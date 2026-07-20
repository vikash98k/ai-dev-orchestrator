"""GitHub integration package.

Provides authenticated access to repositories, issues, and Project V2 boards.
"""

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubError,
    GitHubIssueError,
    GitHubProjectError,
    GitHubRepositoryError,
    IssueAccessDeniedError,
    IssueNotFoundError,
    IssueValidationError,
    ProjectAccessDeniedError,
    ProjectItemNotFoundError,
    ProjectNotFoundError,
    ProjectValidationError,
    RateLimitExceededError,
    RepositoryAccessDeniedError,
    RepositoryNotFoundError,
    RepositoryValidationError,
)
from app.github.issue_manager import IssueManager
from app.github.project_manager import ProjectBoardManager
from app.github.repository_manager import RepositoryManager
from app.github.schemas import (
    IssueDetail,
    IssueSummary,
    ProjectBoard,
    ProjectInfo,
    ProjectItem,
    RepositoryInfo,
)

__all__ = [
    "GitHubClient",
    "GitHubAPIError",
    "GitHubAuthenticationError",
    "GitHubConfigurationError",
    "GitHubError",
    "GitHubIssueError",
    "GitHubProjectError",
    "GitHubRepositoryError",
    "IssueAccessDeniedError",
    "IssueDetail",
    "IssueManager",
    "IssueNotFoundError",
    "IssueSummary",
    "IssueValidationError",
    "ProjectAccessDeniedError",
    "ProjectBoard",
    "ProjectBoardManager",
    "ProjectInfo",
    "ProjectItem",
    "ProjectItemNotFoundError",
    "ProjectNotFoundError",
    "ProjectValidationError",
    "RateLimitExceededError",
    "RepositoryAccessDeniedError",
    "RepositoryInfo",
    "RepositoryManager",
    "RepositoryNotFoundError",
    "RepositoryValidationError",
]
