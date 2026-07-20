"""GitHub integration package.

Provides authenticated access to the GitHub API and repository metadata.
"""

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
)
from app.github.repository_manager import RepositoryInfo, RepositoryManager

__all__ = [
    "GitHubClient",
    "GitHubAPIError",
    "GitHubAuthenticationError",
    "GitHubConfigurationError",
    "GitHubError",
    "RepositoryAccessDeniedError",
    "RepositoryInfo",
    "RepositoryManager",
    "RepositoryNotFoundError",
]
