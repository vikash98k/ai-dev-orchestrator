"""Low-level GitPython adapter for local repository operations.

This module isolates GitPython so :class:`GitWorkspaceManager` stays free of
vendor-specific APIs. It does not talk to the GitHub HTTP API.
"""

from __future__ import annotations

import logging
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import GitError as GitPythonError

from app.git.exceptions import (
    BranchCreationError,
    GitOperationError,
    RepositoryCloneError,
    RepositoryOpenError,
    WorkspaceNotFoundError,
)

logger = logging.getLogger(__name__)


class GitClient:
    """Thin GitPython wrapper used by the workspace manager.

    Designed so future adapters (worktrees, shallow clone, sparse checkout)
    can replace this class without changing :class:`GitWorkspaceManager`.
    """

    def clone(self, remote_url: str, destination: Path) -> Repo:
        """Clone ``remote_url`` into ``destination``.

        Args:
            remote_url: Git remote URL (SSH or HTTPS).
            destination: Absolute local path for the clone.

        Returns:
            Opened :class:`~git.Repo`.

        Raises:
            RepositoryCloneError: If the clone fails.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Repository cloned",
            extra={"destination": str(destination)},
        )
        try:
            return Repo.clone_from(remote_url, destination)
        except (GitCommandError, GitPythonError, OSError) as exc:
            raise RepositoryCloneError(
                f"Failed to clone repository into '{destination}': {exc}"
            ) from exc

    def open(self, path: Path) -> Repo:
        """Open an existing local Git repository.

        Args:
            path: Absolute path to the repository root.

        Returns:
            Opened :class:`~git.Repo`.

        Raises:
            WorkspaceNotFoundError: If the path does not exist.
            RepositoryOpenError: If the path is not a valid Git repo.
        """
        if not path.exists():
            raise WorkspaceNotFoundError(f"Workspace path does not exist: {path}")
        try:
            repo = Repo(path)
        except (InvalidGitRepositoryError, NoSuchPathError, GitPythonError) as exc:
            raise RepositoryOpenError(
                f"Failed to open Git repository at '{path}': {exc}"
            ) from exc
        logger.info("Repository opened", extra={"path": str(path)})
        return repo

    def checkout(self, repo: Repo, branch_name: str) -> None:
        """Checkout an existing local branch.

        Raises:
            GitOperationError: If checkout fails.
        """
        try:
            repo.git.checkout(branch_name)
        except (GitCommandError, GitPythonError) as exc:
            raise GitOperationError(
                f"Failed to checkout branch '{branch_name}': {exc}"
            ) from exc
        logger.info("Switch branch", extra={"branch": branch_name})

    def create_and_checkout_branch(self, repo: Repo, branch_name: str) -> None:
        """Create ``branch_name`` from HEAD and check it out.

        Raises:
            BranchCreationError: If creation fails.
        """
        try:
            repo.git.checkout("-b", branch_name)
        except (GitCommandError, GitPythonError) as exc:
            raise BranchCreationError(
                f"Failed to create branch '{branch_name}': {exc}"
            ) from exc
        logger.info("Create branch", extra={"branch": branch_name})

    def branch_exists(self, repo: Repo, branch_name: str) -> bool:
        """Return True when a local branch exists."""
        return any(ref.name == branch_name for ref in repo.heads)

    def remote_branch_exists(self, repo: Repo, branch_name: str) -> bool:
        """Return True when ``origin/<branch>`` exists locally after fetch."""
        remote_ref = f"origin/{branch_name}"
        return any(ref.name == remote_ref for ref in repo.refs)

    def pull(
        self,
        repo: Repo,
        remote: str = "origin",
        branch: str | None = None,
    ) -> None:
        """Pull latest changes for the current (or specified) branch.

        Raises:
            GitOperationError: If pull fails.
        """
        try:
            if branch:
                repo.remotes[remote].pull(branch)
            else:
                repo.remotes[remote].pull()
        except (GitCommandError, GitPythonError, IndexError) as exc:
            raise GitOperationError(f"Failed to pull latest changes: {exc}") from exc

    def fetch(self, repo: Repo, remote: str = "origin") -> None:
        """Fetch remotes so remote branch discovery stays accurate."""
        try:
            repo.remotes[remote].fetch()
        except (GitCommandError, GitPythonError, IndexError) as exc:
            raise GitOperationError(f"Failed to fetch from '{remote}': {exc}") from exc

    def ensure_local_branch_from_remote(
        self,
        repo: Repo,
        branch_name: str,
        remote: str = "origin",
    ) -> None:
        """Create a local tracking branch from ``origin/<branch>`` if needed."""
        if self.branch_exists(repo, branch_name):
            return
        remote_ref = f"{remote}/{branch_name}"
        if not any(ref.name == remote_ref for ref in repo.refs):
            raise GitOperationError(
                f"Branch '{branch_name}' does not exist locally or on '{remote}'."
            )
        try:
            repo.git.checkout("-b", branch_name, remote_ref)
        except (GitCommandError, GitPythonError) as exc:
            raise GitOperationError(
                f"Failed to create local branch '{branch_name}' "
                f"from '{remote_ref}': {exc}"
            ) from exc

    def is_dirty(self, repo: Repo) -> bool:
        """Return True when there are uncommitted changes."""
        return repo.is_dirty(untracked_files=True)

    def current_branch(self, repo: Repo) -> str:
        """Return the active branch name (or detached HEAD SHA prefix)."""
        try:
            return repo.active_branch.name
        except TypeError:
            return repo.head.commit.hexsha[:8]

    def last_commit_sha(self, repo: Repo) -> str | None:
        """Return the short HEAD SHA when commits exist."""
        try:
            return repo.head.commit.hexsha[:8]
        except ValueError:
            return None

    def remote_url(self, repo: Repo, remote: str = "origin") -> str | None:
        """Return the configured remote URL, if any."""
        try:
            return next(repo.remotes[remote].urls)
        except (IndexError, StopIteration, GitPythonError):
            return None
