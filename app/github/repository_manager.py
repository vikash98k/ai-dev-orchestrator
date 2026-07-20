"""Reusable repository manager for GitHub repository access.

This module is the foundation for future Issue, Pull Request, Branch, and
Workflow managers. It depends on :class:`~app.github.client.GitHubClient`
via dependency injection and never instantiates PyGithub directly.
"""

from __future__ import annotations

import logging

from github.Repository import Repository

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAPIError,
    GitHubRepositoryError,
    RepositoryValidationError,
)
from app.github.schemas import RepositoryInfo

logger = logging.getLogger(__name__)


class RepositoryManager:
    """Access and inspect GitHub repositories.

    Responsibilities:
        - Validate repository identifiers
        - Fetch repository objects via the injected client
        - Check repository existence without raising to callers
        - Expose strongly typed repository metadata

    Example:
        >>> github = GitHubClient()
        >>> manager = RepositoryManager(github)
        >>> info = manager.get_repository_info("vikash98k", "fashion-store-backend")
        >>> print(info.name, info.default_branch)
    """

    def __init__(self, github_client: GitHubClient) -> None:
        """Initialize with an authenticated GitHub client.

        Args:
            github_client: Injected :class:`GitHubClient` used for all API
                calls. Authentication remains the client's concern.
        """
        self._github_client = github_client
        logger.debug("RepositoryManager initialized")

    def get_github_client(self) -> GitHubClient:
        """Return the injected :class:`GitHubClient` used for API access."""
        return self._github_client

    def get_repository(self, owner: str, repo: str) -> Repository:
        """Fetch a repository by owner and name.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            The authenticated PyGithub ``Repository`` object.

        Raises:
            RepositoryValidationError: If ``owner`` or ``repo`` is invalid.
            RepositoryNotFoundError: If the repository does not exist.
            RepositoryAccessDeniedError: If the token cannot access it.
            RateLimitExceededError: If the API rate limit is exceeded.
            GitHubAPIError: For unexpected or transient API failures.
        """
        full_name = self._validated_full_name(owner, repo)
        logger.info("Repository requested", extra={"repository": full_name})
        repository = self._github_client.get_repository(full_name)
        logger.info("Repository found", extra={"repository": full_name})
        return repository

    def repository_exists(self, owner: str, repo: str) -> bool:
        """Return whether a repository exists and is accessible.

        This method never raises. Invalid identifiers, missing repositories,
        permission errors, and unexpected API failures all resolve to
        ``False``.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            ``True`` if the repository can be fetched; otherwise ``False``.
        """
        try:
            self.get_repository(owner, repo)
            return True
        except (GitHubRepositoryError, GitHubAPIError) as exc:
            logger.info(
                "Repository existence check failed",
                extra={
                    "owner": owner,
                    "repo": repo,
                    "reason": type(exc).__name__,
                },
            )
            return False
        except Exception as exc:
            logger.warning(
                "Unexpected error during repository existence check",
                extra={
                    "owner": owner,
                    "repo": repo,
                    "reason": type(exc).__name__,
                },
            )
            return False

    def get_repository_info(self, owner: str, repo: str) -> RepositoryInfo:
        """Fetch and map repository metadata into a Pydantic schema.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            Validated :class:`~app.github.schemas.RepositoryInfo`.

        Raises:
            RepositoryValidationError: If ``owner`` or ``repo`` is invalid.
            RepositoryNotFoundError: If the repository does not exist.
            RepositoryAccessDeniedError: If the token cannot access it.
            RateLimitExceededError: If the API rate limit is exceeded.
            GitHubAPIError: For unexpected or transient API failures.
        """
        repository = self.get_repository(owner, repo)
        info = RepositoryInfo.from_repository(repository)
        logger.info(
            "Repository metadata loaded",
            extra={
                "repository": f"{info.owner}/{info.name}",
                "default_branch": info.default_branch,
                "visibility": info.visibility,
            },
        )
        return info

    @staticmethod
    def _validated_full_name(owner: str, repo: str) -> str:
        """Normalize and validate owner/repo identifiers.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            Canonical ``owner/repo`` string.

        Raises:
            RepositoryValidationError: If either identifier is blank.
        """
        normalized_owner = owner.strip() if isinstance(owner, str) else ""
        normalized_repo = repo.strip() if isinstance(repo, str) else ""
        if not normalized_owner or not normalized_repo:
            raise RepositoryValidationError(
                "Repository owner and name must be non-empty strings."
            )
        if "/" in normalized_owner or "/" in normalized_repo:
            raise RepositoryValidationError(
                "Owner and repository name must not contain '/'."
            )
        return f"{normalized_owner}/{normalized_repo}"
