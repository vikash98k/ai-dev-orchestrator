"""Temporary CLI entry point for workflow task selection.

Configuration is loaded dynamically from the environment::

    GITHUB_TOKEN
    GITHUB_OWNER
    GITHUB_REPO
    GITHUB_PROJECT_NUMBER

Run with::

    python main.py
"""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv

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
    TaskSelectionError,
    WorkflowConfigurationError,
    WorkflowEngine,
    WorkflowScanResult,
)

SEPARATOR = "=" * 52
SECTION = "-" * 44


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


def format_workflow_result(result: WorkflowScanResult) -> str:
    """Build the user-facing workflow selection summary."""
    lines = [
        "Repository",
        "",
        result.repository,
        "",
        "Scanning workflow...",
        "",
        "Found:",
        "",
        f"{result.total_issues} Issues",
        "",
        "Ready:",
        "",
        str(result.ready_count),
        "",
        "Eligible:",
        "",
        str(result.eligible_count),
        "",
        SECTION,
        "",
    ]

    selected = result.selected
    if selected is None:
        lines.extend(["No task selected", ""])
        return "\n".join(lines)

    ticket = selected.ticket_id or f"#{selected.issue_number}"
    lines.extend(
        [
            "Selected Task",
            "",
            "Issue:",
            "",
            ticket,
            "",
            "Title:",
            "",
            selected.title,
            "",
            "Reason:",
            "",
            selected.selection_reason,
            "",
            "Predicted Branch",
            "",
            selected.branch_name,
            "",
            "Score",
            "",
            str(selected.score),
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Authenticate, run workflow selection, and print the decision.

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
        result = engine.scan_and_select(owner, repo, project_number)
    except NoEligibleTaskError as exc:
        logger.info("No eligible task: %s", exc)
        print("Repository")
        print()
        print(os.getenv("GITHUB_REPO", ""))
        print()
        print("Scanning workflow...")
        print()
        print("No eligible Ready tasks found.")
        print()
        print(f"Detail: {exc}")
        print()
        print(SEPARATOR)
        return 0
    except (
        GitHubConfigurationError,
        GitHubAuthenticationError,
        GitHubAPIError,
        GitHubRepositoryError,
        GitHubIssueError,
        GitHubProjectError,
        WorkflowConfigurationError,
        TaskSelectionError,
    ) as exc:
        logger.error("Orchestrator failed: %s", exc)
        print("✗ Failed")
        print(f"Error: {exc}")
        print()
        print(SEPARATOR)
        return 1

    print(format_workflow_result(result))
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
