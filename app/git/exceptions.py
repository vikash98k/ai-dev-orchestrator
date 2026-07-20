"""Custom exceptions for local Git workspace operations."""


class GitError(Exception):
    """Base exception for local Git workspace failures."""


class WorkspaceNotFoundError(GitError):
    """Raised when the expected local repository path does not exist."""


class WorkspaceDirtyError(GitError):
    """Raised when the workspace has uncommitted changes."""


class BranchCreationError(GitError):
    """Raised when a feature branch cannot be created or checked out."""


class RepositoryCloneError(GitError):
    """Raised when cloning a repository fails."""


class RepositoryOpenError(GitError):
    """Raised when an existing local repository cannot be opened."""


class GitOperationError(GitError):
    """Raised for unexpected local Git operation failures."""
