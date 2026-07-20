"""GitHub integration package.

Provides authenticated access to repositories and read-only issue operations.
"""

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubError,
    GitHubIssueError,
    GitHubRepositoryError,
    IssueAccessDeniedError,
    IssueNotFoundError,
    IssueValidationError,
    RateLimitExceededError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
    RepositoryValidationError,
)
from app.github.issue_manager import IssueManager
from app.github.repository_manager import RepositoryManager
from app.github.schemas import IssueDetail, IssueSummary, RepositoryInfo

__all__ = [
    "GitHubClient",
    "GitHubAPIError",
    "GitHubAuthenticationError",
    "GitHubConfigurationError",
    "GitHubError",
    "GitHubIssueError",
    "GitHubRepositoryError",
    "IssueAccessDeniedError",
    "IssueDetail",
    "IssueManager",
    "IssueNotFoundError",
    "IssueSummary",
    "IssueValidationError",
    "RateLimitExceededError",
    "RepositoryAccessDeniedError",
    "RepositoryInfo",
    "RepositoryManager",
    "RepositoryNotFoundError",
    "RepositoryValidationError",
]
