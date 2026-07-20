"""Reusable repository manager for GitHub repository access.

This module belongs to the infrastructure layer. It depends on
:class:`~app.github.client.GitHubClient` for authentication and exposes a
narrow repository surface for higher-level application services.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from github import GithubException
from github.Repository import Repository

from app.github.client import GitHubClient
from app.github.exceptions import (
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RepositoryInfo:
    """Metadata for a GitHub repository."""

    name: str
    owner: str
    description: str | None
    default_branch: str
    visibility: str
    stars: int
    forks: int
    open_issues_count: int
    language: str | None
    created_at: datetime
    updated_at: datetime
    clone_url: str
    ssh_url: str
    private: bool


class RepositoryManager:
    """Access and inspect GitHub repositories.

    Responsibilities:
        - Fetch repository objects via the authenticated client
        - Validate that a repository exists and is accessible
        - Map repository metadata into a structured model

    Example:
        >>> github = GitHubClient()
        >>> manager = RepositoryManager(github)
        >>> info = manager.get_repository_info("vikash98k", "fashion-store-backend")
        >>> print(info.name, info.default_branch)
    """

    def __init__(self, github_client: GitHubClient) -> None:
        """Initialize with an authenticated GitHub client.

        Args:
            github_client: Injected :class:`GitHubClient` instance used for
                all API calls. Authentication remains the client's concern.
        """
        self._github_client = github_client
        logger.debug("RepositoryManager initialized")

    def get_repository(self, owner: str, repo: str) -> Repository:
        """Fetch a repository by owner and name.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            The authenticated PyGithub ``Repository`` object.

        Raises:
            RepositoryNotFoundError: If the repository does not exist.
            RepositoryAccessDeniedError: If the token cannot access it.
        """
        full_name = f"{owner}/{repo}"
        logger.info("Fetching repository", extra={"repository": full_name})

        try:
            repository = self._github_client.get_client().get_repo(full_name)
            logger.info("Repository found", extra={"repository": full_name})
            return repository
        except GithubException as exc:
            self._raise_for_github_error(exc, full_name)
            raise  # pragma: no cover - unreachable, satisfies type checkers

    def get_repository_info(self, owner: str, repo: str) -> RepositoryInfo:
        """Fetch and map repository metadata.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            Structured :class:`RepositoryInfo` for the target repository.

        Raises:
            RepositoryNotFoundError: If the repository does not exist.
            RepositoryAccessDeniedError: If the token cannot access it.
        """
        repository = self.get_repository(owner, repo)
        info = RepositoryInfo(
            name=repository.name,
            owner=repository.owner.login,
            description=repository.description,
            default_branch=repository.default_branch,
            visibility=repository.visibility,
            stars=repository.stargazers_count,
            forks=repository.forks_count,
            open_issues_count=repository.open_issues_count,
            language=repository.language,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
            clone_url=repository.clone_url,
            ssh_url=repository.ssh_url,
            private=repository.private,
        )
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
    def _raise_for_github_error(exc: GithubException, full_name: str) -> None:
        """Translate PyGithub errors into domain exceptions.

        Args:
            exc: The underlying PyGithub exception.
            full_name: ``owner/repo`` identifier used in error messages.

        Raises:
            RepositoryNotFoundError: On HTTP 404.
            RepositoryAccessDeniedError: On HTTP 401 or 403.
            RepositoryAccessDeniedError: For other unexpected API failures.
        """
        status = exc.status
        logger.error(
            "GitHub repository request failed",
            extra={"repository": full_name, "status": status, "message": str(exc)},
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

        raise RepositoryAccessDeniedError(
            f"Failed to access repository '{full_name}' (status={status}): {exc.data}"
        ) from exc
