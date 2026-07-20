"""Temporary CLI entry point for GitHub Project V2 board status.

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
import re
import sys
from collections import defaultdict

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
    IssueSummary,
    ProjectBoard,
    ProjectBoardManager,
    ProjectItem,
    RepositoryManager,
)

SEPARATOR = "=" * 52
SECTION = "-" * 52
_TICKET_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)\b")

# Preferred column order for the CLI board view.
_STATUS_ORDER = (
    "Ready",
    "In Progress",
    "Review",
    "Testing",
    "Done",
    "Backlog",
)


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


def _ticket_label(item: ProjectItem) -> str:
    """Derive a display ticket id from the issue title, else ``#number``."""
    match = _TICKET_RE.match(item.issue_title.strip())
    if match:
        return match.group(1)
    return f"#{item.issue_number}"


def _display_title(item: ProjectItem) -> str:
    """Human title without a leading ticket id prefix."""
    title = item.issue_title.strip()
    match = _TICKET_RE.match(title)
    if not match:
        return title
    remainder = title[match.end() :].lstrip(" :-")
    return remainder or title


def format_open_issues(repo_name: str, issues: list[IssueSummary]) -> str:
    """Build the user-facing open-issues summary for the CLI.

    Args:
        repo_name: Repository name to display.
        issues: Open issue summaries.

    Returns:
        Multi-line summary ready to print.
    """
    lines = [
        "Repository",
        "",
        repo_name,
        "",
        SECTION,
        "",
        "Open Issues",
        "",
    ]

    if not issues:
        lines.extend(["(none)", "", "Total Open Issues: 0", ""])
        return "\n".join(lines)

    for issue in issues:
        assignees = ", ".join(issue.assignees) if issue.assignees else "Unassigned"
        labels = ", ".join(issue.labels) if issue.labels else "(none)"
        lines.extend(
            [
                f"#{issue.number}",
                "",
                "Title:",
                issue.title,
                "",
                "State:",
                issue.state,
                "",
                "Labels:",
                labels,
                "",
                "Assignees:",
                assignees,
                "",
                "Created:",
                issue.created_at.date().isoformat(),
                "",
                "URL:",
                issue.url,
                "",
                SECTION,
                "",
            ]
        )

    lines.append(f"Total Open Issues: {len(issues)}")
    lines.append("")
    return "\n".join(lines)


def format_project_board(repo_name: str, board: ProjectBoard) -> str:
    """Build the user-facing project board summary for the CLI.

    Args:
        repo_name: Repository name to display.
        board: Loaded project board snapshot.

    Returns:
        Multi-line summary ready to print.
    """
    grouped: dict[str, list[ProjectItem]] = defaultdict(list)
    for item in board.items:
        key = item.status or "Unassigned"
        grouped[key].append(item)

    ordered_statuses: list[str] = []
    for status in _STATUS_ORDER:
        for key in list(grouped):
            if key.casefold() == status.casefold():
                ordered_statuses.append(key)
                break
    for key in sorted(grouped):
        if key not in ordered_statuses:
            ordered_statuses.append(key)

    lines = [
        "Repository:",
        repo_name,
        "",
        "Project:",
        board.project.title,
        "",
        SECTION,
        "",
    ]

    if not board.items:
        lines.extend(["(no project items)", ""])
        return "\n".join(lines)

    for status in ordered_statuses:
        lines.append(status.upper())
        lines.append("")
        for item in grouped[status]:
            lines.append(_ticket_label(item))
            lines.append(_display_title(item))
            lines.append("")
        lines.append(SECTION)
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    """Authenticate, load the project board, and print status columns.

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
        print("✓ Connected to GitHub")
        print()

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
        board = project_manager.get_board(owner, project_number)
    except (
        GitHubConfigurationError,
        GitHubAuthenticationError,
        GitHubAPIError,
        GitHubRepositoryError,
        GitHubIssueError,
        GitHubProjectError,
    ) as exc:
        logger.error("Orchestrator failed: %s", exc)
        print("✗ Failed")
        print(f"Error: {exc}")
        print()
        print(SEPARATOR)
        return 1

    print(format_project_board(repo, board))
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
