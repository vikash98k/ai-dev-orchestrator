"""GitHub integration package.

Provides authenticated access to the GitHub API and repository metadata.
"""

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubError,
    GitHubRepositoryError,
    RateLimitExceededError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
    RepositoryValidationError,
)
from app.github.repository_manager import RepositoryManager
from app.github.schemas import RepositoryInfo

__all__ = [
    "GitHubClient",
    "GitHubAPIError",
    "GitHubAuthenticationError",
    "GitHubConfigurationError",
    "GitHubError",
    "GitHubRepositoryError",
    "RateLimitExceededError",
    "RepositoryAccessDeniedError",
    "RepositoryInfo",
    "RepositoryManager",
    "RepositoryNotFoundError",
    "RepositoryValidationError",
]
