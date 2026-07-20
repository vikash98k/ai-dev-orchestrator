"""Git workspace manager for preparing local repositories.

Decision and GitHub API concerns stay outside this module. It only prepares
local clones for later AI implementation steps.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from git import Repo

from app.git.exceptions import (
    BranchCreationError,
    GitOperationError,
    RepositoryOpenError,
    WorkspaceDirtyError,
    WorkspaceNotFoundError,
)
from app.git.git_client import GitClient
from app.git.schemas import WorkspaceInfo

logger = logging.getLogger(__name__)


class GitWorkspaceManager:
    """Prepare a local Git workspace for a selected implementation task.

    Responsibilities:
        - Resolve workspace paths under a configured root
        - Clone missing repositories
        - Checkout the default branch and pull latest
        - Create or reuse a feature branch supplied by the workflow engine
        - Report workspace status

    Example:
        >>> manager = GitWorkspaceManager(workspace_root="~/workspace")
        >>> info = manager.prepare_workspace(
        ...     repository_name="fashion-store-backend",
        ...     remote_url="git@github.com:vikash98k/fashion-store-backend.git",
        ...     feature_branch="feature/AUTH-001-user-model",
        ...     default_branch="develop",
        ... )
    """

    def __init__(
        self,
        workspace_root: str | Path | None = None,
        *,
        git_client: GitClient | None = None,
    ) -> None:
        """Initialize with a workspace root and optional Git adapter.

        Args:
            workspace_root: Root directory for clones. Defaults to
                ``WORKSPACE_ROOT`` env var or ``~/workspace``.
            git_client: Optional injected :class:`GitClient` (tests / future
                adapters for worktrees, shallow clones, etc.).
        """
        root = workspace_root or os.getenv("WORKSPACE_ROOT") or "~/workspace"
        self._workspace_root = Path(root).expanduser().resolve()
        self._git = git_client or GitClient()
        self._repo: Repo | None = None
        self._repository_name: str | None = None
        self._default_branch: str | None = None
        self._feature_branch: str | None = None
        logger.debug(
            "GitWorkspaceManager initialized",
            extra={"workspace_root": str(self._workspace_root)},
        )

    @property
    def workspace_root(self) -> Path:
        """Absolute workspace root directory."""
        return self._workspace_root

    def repository_path(self, repository_name: str) -> Path:
        """Return the absolute local path for a repository name."""
        safe_name = repository_name.strip().strip("/")
        if not safe_name or "/" in safe_name or safe_name in {".", ".."}:
            raise GitOperationError(
                f"Invalid repository_name for workspace path: {repository_name!r}"
            )
        return self._workspace_root / safe_name

    def clone_repository(self, remote_url: str, repository_name: str) -> Repo:
        """Clone a repository when the local path does not already exist.

        Args:
            remote_url: Git remote URL.
            repository_name: Directory name under the workspace root.

        Returns:
            Opened repository (existing or newly cloned).
        """
        path = self.repository_path(repository_name)
        if path.exists():
            logger.info("Workspace found", extra={"path": str(path)})
            return self.open_repository(repository_name)

        repo = self._git.clone(remote_url, path)
        self._repo = repo
        self._repository_name = repository_name
        return repo

    def open_repository(self, repository_name: str) -> Repo:
        """Open an existing local repository under the workspace root."""
        path = self.repository_path(repository_name)
        if not path.exists():
            raise WorkspaceNotFoundError(
                f"Local repository not found at '{path}'. Clone it first."
            )
        logger.info("Workspace found", extra={"path": str(path)})
        repo = self._git.open(path)
        self._repo = repo
        self._repository_name = repository_name
        return repo

    def checkout_default_branch(self, default_branch: str) -> None:
        """Checkout the configured default branch (e.g. develop)."""
        repo = self._require_open_repo()
        self._git.fetch(repo)
        self._git.ensure_local_branch_from_remote(repo, default_branch)
        self._git.checkout(repo, default_branch)
        self._default_branch = default_branch
        logger.info("Checkout develop", extra={"branch": default_branch})

    def pull_latest(self, branch: str | None = None) -> None:
        """Pull latest changes for the current or specified branch."""
        repo = self._require_open_repo()
        target = branch or self._default_branch or self._git.current_branch(repo)
        self._git.pull(repo, branch=target)
        logger.info("Pull latest", extra={"branch": target})

    def create_feature_branch(self, branch_name: str) -> None:
        """Create ``branch_name`` or checkout it when it already exists.

        The branch name must be supplied by the workflow engine.
        """
        if not branch_name or not branch_name.strip():
            raise BranchCreationError("feature branch name must be non-empty.")
        normalized = branch_name.strip()
        repo = self._require_open_repo()

        if self._git.branch_exists(repo, normalized):
            logger.info(
                "Switch branch",
                extra={"branch": normalized, "reason": "already_exists"},
            )
            self._git.checkout(repo, normalized)
        else:
            logger.info("Create branch", extra={"branch": normalized})
            self._git.create_and_checkout_branch(repo, normalized)

        self._feature_branch = normalized

    def switch_branch(self, branch_name: str) -> None:
        """Switch to an existing local branch."""
        repo = self._require_open_repo()
        if not self._git.branch_exists(repo, branch_name):
            raise GitOperationError(f"Local branch '{branch_name}' does not exist.")
        self._git.checkout(repo, branch_name)
        logger.info("Switch branch", extra={"branch": branch_name})

    def validate_clean_workspace(self) -> None:
        """Raise :class:`WorkspaceDirtyError` when uncommitted changes exist."""
        repo = self._require_open_repo()
        if self._git.is_dirty(repo):
            logger.info("Workspace dirty", extra={"path": str(repo.working_tree_dir)})
            raise WorkspaceDirtyError(
                f"Workspace has uncommitted changes: {repo.working_tree_dir}"
            )
        logger.info("Workspace clean", extra={"path": str(repo.working_tree_dir)})

    def workspace_status(self) -> WorkspaceInfo:
        """Return a :class:`WorkspaceInfo` snapshot for the open repository."""
        repo = self._require_open_repo()
        if not self._repository_name:
            raise GitOperationError("Repository name is not set on the manager.")
        dirty = self._git.is_dirty(repo)
        return WorkspaceInfo(
            repository_name=self._repository_name,
            local_path=str(Path(repo.working_tree_dir or "").resolve()),
            current_branch=self._git.current_branch(repo),
            default_branch=self._default_branch or self._git.current_branch(repo),
            feature_branch=self._feature_branch,
            is_clean=not dirty,
            has_uncommitted_changes=dirty,
            last_commit=self._git.last_commit_sha(repo),
            remote_url=self._git.remote_url(repo),
        )

    def prepare_workspace(
        self,
        *,
        repository_name: str,
        remote_url: str,
        feature_branch: str,
        default_branch: str,
    ) -> WorkspaceInfo:
        """Clone/open, update default branch, and create the feature branch.

        Args:
            repository_name: Local folder name under the workspace root.
            remote_url: Git remote used when cloning.
            feature_branch: Branch name from the workflow engine.
            default_branch: Branch to update before branching (e.g. develop).

        Returns:
            Final :class:`WorkspaceInfo` on the feature branch.
        """
        path = self.repository_path(repository_name)
        if path.exists():
            logger.info("Workspace found", extra={"path": str(path)})
            self.open_repository(repository_name)
        else:
            self.clone_repository(remote_url, repository_name)

        self.validate_clean_workspace()
        self.checkout_default_branch(default_branch)
        self.pull_latest(default_branch)
        self.validate_clean_workspace()
        self.create_feature_branch(feature_branch)
        return self.workspace_status()

    def _require_open_repo(self) -> Repo:
        """Return the in-memory repo or raise if none is open."""
        if self._repo is None:
            raise RepositoryOpenError(
                "No repository is open. Call clone_repository() or open_repository()."
            )
        return self._repo
