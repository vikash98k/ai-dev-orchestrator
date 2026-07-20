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
from github import Auth, Github, GithubException
from github.Repository import Repository

from app.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConfigurationError,
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
            load_dotenv()
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
                extra={"status": exc.status, "message": str(exc)},
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
            GitHubAPIError: For unexpected or transient API failures.
        """
        try:
            return self._client.get_repo(full_name)
        except GithubException as exc:
            status = exc.status
            logger.error(
                "GitHub repository request failed",
                extra={
                    "repository": full_name,
                    "status": status,
                    "message": str(exc),
                },
            )
            if status == 404:
                raise RepositoryNotFoundError(
                    f"Repository '{full_name}' was not found."
                ) from exc
            if status in {401, 403}:
                raise RepositoryAccessDeniedError(
                    f"Access denied for repository '{full_name}' "
                    f"(status={status}). Check token permissions."
                ) from exc
            raise GitHubAPIError(
                f"Unexpected GitHub API error for repository '{full_name}' "
                f"(status={status}): {exc.data}"
            ) from exc
