"""Reusable GitHub client for authenticated API access.

This module belongs to the infrastructure layer. It wraps PyGithub and exposes
a narrow authentication and repository-fetch surface that higher-level
application services can depend on without coupling to PyGithub internals.
"""

from __future__ import annotations

import logging
import os
from typing import TypedDict

from dotenv import load_dotenv
from github import (
    Auth,
    Github,
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
)
from github.Repository import Repository
from requests.exceptions import RequestException

from app.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConfigurationError,
    RateLimitExceededError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
)

logger = logging.getLogger(__name__)


class AuthenticatedUser(TypedDict):
    """Identity details for an authenticated GitHub user."""

    username: str
    id: int


class GitHubClient:
    """Authenticate against GitHub using a Fine-Grained Personal Access Token.

    Responsibilities:
        - Load ``GITHUB_TOKEN`` from the environment
        - Create an authenticated PyGithub ``Github`` instance
        - Verify the connection by fetching the authenticated user
        - Fetch repositories and translate PyGithub errors into domain errors
        - Expose the authenticated client for future use

    Example:
        >>> client = GitHubClient()
        >>> user = client.verify_connection()
        >>> print(user["username"], user["id"])
    """

    def __init__(self, token: str | None = None, *, load_env: bool = True) -> None:
        """Initialize the client and create an authenticated GitHub session.

        Args:
            token: Optional explicit token. When omitted, the token is read
                from the ``GITHUB_TOKEN`` environment variable.
            load_env: When ``True``, load variables from a local ``.env`` file
                before reading the environment.

        Raises:
            GitHubConfigurationError: If no token is available.
            GitHubAuthenticationError: If the token cannot create a session.
        """
        if load_env:
            load_dotenv(override=True)
            logger.debug("Loaded environment variables from .env if present")

        self._token = token or os.getenv("GITHUB_TOKEN")
        if not self._token:
            logger.error("GITHUB_TOKEN is not set")
            raise GitHubConfigurationError(
                "GITHUB_TOKEN environment variable is not set. "
                "Copy .env.example to .env and provide a Fine-Grained PAT."
            )

        try:
            auth = Auth.Token(self._token)
            self._client = Github(auth=auth)
            logger.info("GitHub client created successfully")
        except Exception as exc:
            logger.exception("Failed to create authenticated GitHub client")
            raise GitHubAuthenticationError(
                f"Failed to create GitHub client: {exc}"
            ) from exc

    def get_client(self) -> Github:
        """Return the authenticated PyGithub ``Github`` instance.

        Returns:
            Authenticated ``Github`` client ready for API calls.
        """
        return self._client

    def execute_graphql(
        self,
        query: str,
        variables: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Execute a GitHub GraphQL query via the authenticated client.

        Required for Project V2 and other GraphQL-only resources.

        Args:
            query: GraphQL query string.
            variables: Optional GraphQL variables.

        Returns:
            The ``data`` object from the GraphQL response.

        Raises:
            RateLimitExceededError: If the API rate limit is exceeded.
            GitHubAPIError: For GraphQL, network, or unexpected failures.
        """
        try:
            _headers, payload = self._client._Github__requester.graphql_query(
                query=query,
                variables=variables or {},
            )
        except RateLimitExceededException as exc:
            logger.error(
                "Unexpected API failures",
                extra={"status": exc.status, "kind": "rate_limit"},
            )
            raise RateLimitExceededError(
                "GitHub API rate limit exceeded during GraphQL request."
            ) from exc
        except UnknownObjectException as exc:
            logger.error(
                "Unexpected API failures",
                extra={"status": exc.status, "kind": "not_found", "detail": str(exc)},
            )
            raise GitHubAPIError(
                f"GitHub GraphQL resource not found (status={exc.status}): {exc.data}"
            ) from exc
        except GithubException as exc:
            logger.error(
                "Unexpected API failures",
                extra={"status": exc.status, "detail": str(exc)},
            )
            raise GitHubAPIError(
                f"GitHub GraphQL request failed (status={exc.status}): {exc.data}"
            ) from exc
        except RequestException as exc:
            logger.error(
                "Unexpected API failures",
                extra={"detail": str(exc), "kind": "network"},
            )
            raise GitHubAPIError(
                f"Network failure during GitHub GraphQL request: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise GitHubAPIError("Unexpected GraphQL response payload type.")

        errors = payload.get("errors")
        if errors:
            logger.error(
                "Unexpected API failures",
                extra={"graphql_errors": errors},
            )
            raise GitHubAPIError(f"GitHub GraphQL returned errors: {errors}")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise GitHubAPIError("GitHub GraphQL response missing data object.")
        return data

    def verify_connection(self) -> AuthenticatedUser:
        """Verify authentication by fetching the authenticated user.

        Returns:
            A mapping with ``username`` and ``id`` of the authenticated user.

        Raises:
            GitHubAuthenticationError: If authentication or the API call fails.
        """
        try:
            user = self._client.get_user()
            result: AuthenticatedUser = {
                "username": user.login,
                "id": user.id,
            }
            logger.info(
                "GitHub authentication verified",
                extra={"username": result["username"], "user_id": result["id"]},
            )
            return result
        except GithubException as exc:
            logger.error(
                "GitHub authentication failed",
                extra={"status": exc.status, "detail": str(exc)},
            )
            raise GitHubAuthenticationError(
                f"GitHub authentication failed (status={exc.status}): {exc.data}"
            ) from exc
        except Exception as exc:
            logger.exception("Unexpected error while verifying GitHub connection")
            raise GitHubAuthenticationError(
                f"Unexpected error verifying GitHub connection: {exc}"
            ) from exc

    def get_repository(self, full_name: str) -> Repository:
        """Fetch a repository by its ``owner/repo`` full name.

        Args:
            full_name: Repository identifier in ``owner/repo`` form.

        Returns:
            The authenticated PyGithub ``Repository`` object.

        Raises:
            RepositoryNotFoundError: If the repository does not exist.
            RepositoryAccessDeniedError: If the token cannot access it.
            RateLimitExceededError: If the GitHub API rate limit is hit.
            GitHubAPIError: For unexpected or transient API failures.
        """
        try:
            return self._client.get_repo(full_name)
        except UnknownObjectException as exc:
            logger.error(
                "Repository not found",
                extra={"repository": full_name, "status": exc.status},
            )
            raise RepositoryNotFoundError(
                f"Repository '{full_name}' was not found."
            ) from exc
        except RateLimitExceededException as exc:
            # Placeholder: future workflow engine can attach retry/backoff here.
            logger.error(
                "GitHub API rate limit exceeded",
                extra={"repository": full_name, "status": exc.status},
            )
            raise RateLimitExceededError(
                f"GitHub API rate limit exceeded while accessing "
                f"repository '{full_name}'."
            ) from exc
        except GithubException as exc:
            status = exc.status
            if status == 404:
                logger.error(
                    "Repository not found",
                    extra={"repository": full_name, "status": status},
                )
                raise RepositoryNotFoundError(
                    f"Repository '{full_name}' was not found."
                ) from exc
            if status in {401, 403}:
                logger.error(
                    "Permission denied",
                    extra={"repository": full_name, "status": status},
                )
                raise RepositoryAccessDeniedError(
                    f"Access denied for repository '{full_name}' "
                    f"(status={status}). Check token permissions."
                ) from exc
            logger.error(
                "Unexpected API errors",
                extra={
                    "repository": full_name,
                    "status": status,
                    "detail": str(exc),
                },
            )
            raise GitHubAPIError(
                f"Unexpected GitHub API error for repository '{full_name}' "
                f"(status={status}): {exc.data}"
            ) from exc
        except RequestException as exc:
            logger.error(
                "Unexpected API errors",
                extra={"repository": full_name, "detail": str(exc)},
            )
            raise GitHubAPIError(
                f"Network failure while accessing repository '{full_name}': {exc}"
            ) from exc
