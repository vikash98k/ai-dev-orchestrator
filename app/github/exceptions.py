"""Custom exceptions for the GitHub integration layer."""


class GitHubError(Exception):
    """Base exception for all GitHub-related errors."""


class GitHubConfigurationError(GitHubError):
    """Raised when required GitHub configuration is missing or invalid."""


class GitHubAuthenticationError(GitHubError):
    """Raised when GitHub authentication fails."""


class GitHubAPIError(GitHubError):
    """Raised for unexpected or transient GitHub API failures."""


class GitHubRepositoryError(GitHubError):
    """Base exception for repository-scoped failures."""


class RepositoryNotFoundError(GitHubRepositoryError):
    """Raised when the requested GitHub repository does not exist."""


class RepositoryAccessDeniedError(GitHubRepositoryError):
    """Raised when the token cannot access the requested repository."""


class RepositoryValidationError(GitHubRepositoryError):
    """Raised when repository owner/name inputs are invalid."""


class RateLimitExceededError(GitHubAPIError):
    """Raised when the GitHub API rate limit has been exceeded.

    Placeholder for a future retry/backoff strategy in the workflow engine.
    """


class GitHubIssueError(GitHubError):
    """Base exception for issue-scoped failures."""


class IssueNotFoundError(GitHubIssueError):
    """Raised when the requested GitHub issue does not exist."""


class IssueAccessDeniedError(GitHubIssueError):
    """Raised when the token cannot access the requested issue."""


class IssueValidationError(GitHubIssueError):
    """Raised when issue query inputs are invalid."""


class GitHubProjectError(GitHubError):
    """Base exception for GitHub Project V2 failures."""


class ProjectNotFoundError(GitHubProjectError):
    """Raised when the requested GitHub Project V2 does not exist."""


class ProjectItemNotFoundError(GitHubProjectError):
    """Raised when a project item for an issue cannot be found."""


class ProjectAccessDeniedError(GitHubProjectError):
    """Raised when the token cannot access the requested project."""


class ProjectValidationError(GitHubProjectError):
    """Raised when project query inputs are invalid."""
