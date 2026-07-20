"""Temporary CLI entry point for GitHub auth and open-issue listing.

Configuration is loaded dynamically from the environment::

    GITHUB_TOKEN
    GITHUB_OWNER
    GITHUB_REPO

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
    GitHubRepositoryError,
    IssueManager,
    IssueSummary,
    RepositoryManager,
)

SEPARATOR = "=" * 54
SECTION = "-" * 54


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
        assignee = issue.assignees[0] if issue.assignees else "Unassigned"
        labels = "\n".join(issue.labels) if issue.labels else "(none)"
        lines.extend(
            [
                f"#{issue.number}",
                "",
                "Title:",
                issue.title,
                "",
                "Labels:",
                labels,
                "",
                "Assignee:",
                assignee,
                "",
                "Created:",
                issue.created_at.date().isoformat(),
                "",
                SECTION,
                "",
            ]
        )

    lines.append(f"Total Open Issues: {len(issues)}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """Authenticate, list open issues, and print a summary.

    Returns:
        Process exit code (``0`` on success, ``1`` on failure).
    """
    configure_logging()
    logger = logging.getLogger(__name__)
    load_dotenv()

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

        repository_manager = RepositoryManager(client)
        issue_manager = IssueManager(repository_manager)
        open_issues = issue_manager.list_open_issues(owner, repo)
    except (
        GitHubConfigurationError,
        GitHubAuthenticationError,
        GitHubAPIError,
        GitHubRepositoryError,
        GitHubIssueError,
    ) as exc:
        logger.error("Orchestrator failed: %s", exc)
        print("✗ Failed")
        print(f"Error: {exc}")
        print()
        print(SEPARATOR)
        return 1

    print(format_open_issues(repo, open_issues))
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
