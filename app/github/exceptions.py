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
