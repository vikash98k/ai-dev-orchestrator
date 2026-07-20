"""Temporary CLI entry point for GitHub auth and repository metadata.

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
    GitHubRepositoryError,
    RepositoryInfo,
    RepositoryManager,
)

SEPARATOR = "=" * 51


def configure_logging() -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def _require_env(name: str) -> str:
    """Return a required environment variable or raise a configuration error.

    Args:
        name: Environment variable name.

    Returns:
        Non-empty trimmed value.

    Raises:
        GitHubConfigurationError: If the variable is missing or blank.
    """
    value = (os.getenv(name) or "").strip()
    if not value:
        raise GitHubConfigurationError(
            f"{name} environment variable is not set. "
            f"Add it to your .env file (see .env.example)."
        )
    return value


def format_repository_summary(info: RepositoryInfo) -> str:
    """Build the user-facing repository summary for the CLI.

    Args:
        info: Structured repository metadata.

    Returns:
        Multi-line summary ready to print.
    """
    fields = (
        ("Name", info.name),
        ("Owner", info.owner),
        ("Visibility", info.visibility.capitalize()),
        ("Default Branch", info.default_branch),
        ("Language", info.language or "N/A"),
        ("Stars", info.stars),
        ("Forks", info.forks),
        ("Open Issues", info.open_issues_count),
        ("Created", info.created_at.date().isoformat()),
        ("Updated", info.updated_at.date().isoformat()),
    )
    lines = [
        "✓ Repository Found",
        "",
        "Repository Information",
        "",
    ]
    for label, value in fields:
        lines.extend([f"{label}:", str(value), ""])
    return "\n".join(lines)


def main() -> int:
    """Authenticate, load repository metadata, and print a summary.

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
    print("Connecting to GitHub...")
    print()

    try:
        client = GitHubClient(load_env=False)
        client.verify_connection()
        print("✓ Authentication Successful")
        print()

        owner = _require_env("GITHUB_OWNER")
        repo = _require_env("GITHUB_REPO")

        print("Loading Repository...")
        print()

        manager = RepositoryManager(client)
        info = manager.get_repository_info(owner, repo)
    except (
        GitHubConfigurationError,
        GitHubAuthenticationError,
        GitHubAPIError,
        GitHubRepositoryError,
    ) as exc:
        logger.error("Orchestrator failed: %s", exc)
        print("✗ Failed")
        print(f"Error: {exc}")
        print()
        print(SEPARATOR)
        return 1

    print(format_repository_summary(info))
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
