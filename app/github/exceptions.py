"""Custom exceptions for the GitHub integration layer."""


class GitHubError(Exception):
    """Base exception for all GitHub-related errors."""


class GitHubConfigurationError(GitHubError):
    """Raised when required GitHub configuration is missing or invalid."""


class GitHubAuthenticationError(GitHubError):
    """Raised when GitHub authentication fails."""


class RepositoryNotFoundError(GitHubError):
    """Raised when the requested GitHub repository does not exist."""


class RepositoryAccessDeniedError(GitHubError):
    """Raised when the token cannot access the requested repository."""
