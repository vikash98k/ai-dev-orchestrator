"""GitHub integration package.

Provides authenticated access to the GitHub API via a reusable client.
"""

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAuthenticationError,
    GitHubConfigurationError,
    GitHubError,
)

__all__ = [
    "GitHubClient",
    "GitHubAuthenticationError",
    "GitHubConfigurationError",
    "GitHubError",
]
