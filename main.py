"""Temporary CLI entry point for workspace preparation.

Configuration::

    GITHUB_TOKEN
    GITHUB_OWNER
    GITHUB_REPO
    GITHUB_PROJECT_NUMBER
    WORKSPACE_ROOT
    GIT_DEFAULT_BRANCH   # optional override; defaults to repo default branch

Run with::

    python main.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.git import (
    BranchCreationError,
    GitError,
    GitOperationError,
    GitWorkspaceManager,
    RepositoryCloneError,
    RepositoryOpenError,
    WorkspaceDirtyError,
    WorkspaceInfo,
    WorkspaceNotFoundError,
)
from app.github import (
    GitHubAPIError,
    GitHubAuthenticationError,
    GitHubClient,
    GitHubConfigurationError,
    GitHubIssueError,
    GitHubProjectError,
    GitHubRepositoryError,
    IssueManager,
    ProjectBoardManager,
    RepositoryManager,
)
from app.workflow import (
    NoEligibleTaskError,
    SelectedTask,
    TaskSelectionError,
    WorkflowConfigurationError,
    WorkflowEngine,
)

SEPARATOR = "=" * 52


def configure_logging() -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def _require_env(name: str) -> str:
    """Return a required environment variable or raise a configuration error."""
    value = (os.getenv(name) or "").strip()
    if not value:
        raise GitHubConfigurationError(
            f"{name} environment variable is not set. "
            f"Add it to your .env file (see .env.example)."
        )
    return value


def _require_project_number() -> int:
    """Parse ``GITHUB_PROJECT_NUMBER`` as a positive integer."""
    raw = _require_env("GITHUB_PROJECT_NUMBER")
    try:
        number = int(raw)
    except ValueError as exc:
        raise GitHubConfigurationError(
            "GITHUB_PROJECT_NUMBER must be an integer."
        ) from exc
    if number <= 0:
        raise GitHubConfigurationError(
            "GITHUB_PROJECT_NUMBER must be a positive integer."
        )
    return number


def _display_path(path: str) -> str:
    """Render a path with ``~`` when under the user home directory."""
    home = str(Path.home())
    if path.startswith(home):
        return "~" + path[len(home) :]
    return path


def format_workspace_ready(
    repo_name: str,
    default_branch: str,
    feature_branch: str,
    info: WorkspaceInfo,
) -> str:
    """Build the user-facing workspace preparation summary."""
    return "\n".join(
        [
            "Repository",
            "",
            repo_name,
            "",
            "Workspace",
            "",
            "✓ Repository Found",
            "",
            "Location",
            "",
            _display_path(info.local_path),
            "",
            "Branch",
            "",
            default_branch,
            "",
            "Pulling latest...",
            "",
            "✓ Up To Date",
            "",
            "Creating Feature Branch...",
            "",
            f"✓ {feature_branch}",
            "",
            "Workspace Status",
            "",
            "Clean" if info.is_clean else "Dirty",
            "",
            "Ready for AI Implementation",
            "",
        ]
    )


def main() -> int:
    """Select a task, prepare the local Git workspace, and print status.

    Returns:
        Process exit code (``0`` on success, ``1`` on failure).
    """
    configure_logging()
    logger = logging.getLogger(__name__)
    load_dotenv(override=True)

    print(SEPARATOR)
    print()
    print("AI Dev Orchestrator")
    print()

    try:
        client = GitHubClient(load_env=False)
        client.verify_connection()

        owner = _require_env("GITHUB_OWNER")
        repo = _require_env("GITHUB_REPO")
        project_number = _require_project_number()

        repository_manager = RepositoryManager(client)
        issue_manager = IssueManager(repository_manager)
        project_manager = ProjectBoardManager(
            client,
            repository_manager,
            issue_manager,
        )
        engine = WorkflowEngine(
            repository_manager,
            issue_manager,
            project_manager,
        )

        try:
            selected: SelectedTask = engine.select_next_task(
                owner,
                repo,
                project_number,
            )
        except NoEligibleTaskError:
            logger.info("No eligible workflow task; using demo feature branch")
            selected = SelectedTask(
                issue_number=0,
                title="Demo Workspace Preparation",
                selection_reason="No Ready tasks — demo branch only",
                branch_name="feature/DEMO-000-workspace-prep",
                estimated_priority=None,
                score=0.0,
                ticket_id="DEMO-000",
            )

        repo_info = repository_manager.get_repository_info(owner, repo)
        default_branch = (
            os.getenv("GIT_DEFAULT_BRANCH") or ""
        ).strip() or repo_info.default_branch
        remote_url = repo_info.ssh_url or repo_info.clone_url

        workspace_manager = GitWorkspaceManager()
        info = workspace_manager.prepare_workspace(
            repository_name=repo,
            remote_url=remote_url,
            feature_branch=selected.branch_name,
            default_branch=default_branch,
        )
    except (
        GitHubConfigurationError,
        GitHubAuthenticationError,
        GitHubAPIError,
        GitHubRepositoryError,
        GitHubIssueError,
        GitHubProjectError,
        WorkflowConfigurationError,
        TaskSelectionError,
        WorkspaceNotFoundError,
        WorkspaceDirtyError,
        BranchCreationError,
        RepositoryCloneError,
        RepositoryOpenError,
        GitOperationError,
        GitError,
    ) as exc:
        logger.error("Orchestrator failed: %s", exc)
        print("✗ Failed")
        print(f"Error: {exc}")
        print()
        print(SEPARATOR)
        return 1

    print(format_workspace_ready(repo, default_branch, selected.branch_name, info))
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
