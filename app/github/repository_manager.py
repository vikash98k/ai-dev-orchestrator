"""Reusable repository manager for GitHub repository access.

This module belongs to the infrastructure layer. It depends on
:class:`~app.github.client.GitHubClient` for authentication and repository
fetching, and exposes a narrow metadata surface for higher-level services.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from github.Repository import Repository

from app.github.client import GitHubClient

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

    @classmethod
    def from_repository(cls, repository: Repository) -> RepositoryInfo:
        """Map a PyGithub ``Repository`` into a structured metadata model.

        Args:
            repository: Authenticated PyGithub repository object.

        Returns:
            Immutable :class:`RepositoryInfo` populated from the API object.
        """
        return cls(
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


class RepositoryManager:
    """Access and inspect GitHub repositories.

    Responsibilities:
        - Fetch repository objects via the authenticated client
        - Validate that a repository exists and is accessible
        - Expose structured repository metadata

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
                all API calls. Authentication and error translation remain
                the client's concern.
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
            GitHubAPIError: For unexpected or transient API failures.
        """
        full_name = f"{owner}/{repo}"
        logger.info("Fetching repository", extra={"repository": full_name})
        repository = self._github_client.get_repository(full_name)
        logger.info("Repository found", extra={"repository": full_name})
        return repository

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
