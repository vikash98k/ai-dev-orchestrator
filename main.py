"""Temporary CLI entry point for verifying GitHub authentication.

Run with::

    python main.py
"""

from __future__ import annotations

import logging
import sys

from app.github import (
    GitHubAuthenticationError,
    GitHubClient,
    GitHubConfigurationError,
)

SEPARATOR = "-" * 49


def configure_logging() -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
    )


def main() -> int:
    """Authenticate with GitHub and print connection details.

    Returns:
        Process exit code (``0`` on success, ``1`` on failure).
    """
    configure_logging()
    logger = logging.getLogger(__name__)

    print(SEPARATOR)
    print("AI Dev Orchestrator")
    print("Connecting to GitHub...")
    print()

    try:
        client = GitHubClient()
        user = client.verify_connection()
    except (GitHubConfigurationError, GitHubAuthenticationError) as exc:
        logger.error("GitHub connection failed: %s", exc)
        print("✗ Connection failed")
        print(f"Error: {exc}")
        print(SEPARATOR)
        return 1

    print("✓ Connected successfully")
    print()
    print("Authenticated User:")
    print(f"Username: {user['username']}")
    print(f"ID: {user['id']}")
    print(SEPARATOR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
