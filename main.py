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
    GitHubAuthenticationError,
    GitHubClient,
    GitHubConfigurationError,
    RepositoryAccessDeniedError,
    RepositoryManager,
    RepositoryNotFoundError,
)

SEPARATOR = "-" * 40


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
        print("✓ Connected")
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
        RepositoryNotFoundError,
        RepositoryAccessDeniedError,
    ) as exc:
        logger.error("Orchestrator failed: %s", exc)
        print("✗ Failed")
        print(f"Error: {exc}")
        print()
        print(SEPARATOR)
        return 1

    print("✓ Repository Found")
    print()
    print("Repository")
    print()
    print("Name:")
    print(info.name)
    print()
    print("Owner:")
    print(info.owner)
    print()
    print("Default Branch:")
    print(info.default_branch)
    print()
    print("Visibility:")
    print(info.visibility.capitalize())
    print()
    print("Language:")
    print(info.language or "N/A")
    print()
    print("Stars:")
    print(info.stars)
    print()
    print("Open Issues:")
    print(info.open_issues_count)
    print()
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
