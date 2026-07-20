"""GraphQL transport adapter for GitHub API access.

Isolates PyGithub's GraphQL entrypoint so callers depend on a narrow
protocol instead of PyGithub requester internals.
"""

from __future__ import annotations

from typing import Any, Protocol

from github import Github


class GraphQLTransport(Protocol):
    """Minimal contract for executing GitHub GraphQL queries."""

    def execute(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run a GraphQL query and return ``(headers, payload)``."""


class PyGithubGraphQLTransport:
    """Adapter over PyGithub's public ``Github.requester.graphql_query`` API."""

    def __init__(self, github: Github) -> None:
        """Bind to an authenticated PyGithub client.

        Args:
            github: Authenticated :class:`~github.Github` instance.
        """
        self._github = github

    def execute(
        self,
        query: str,
        variables: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Execute a GraphQL query through PyGithub's public requester.

        Args:
            query: GraphQL query string.
            variables: GraphQL variables map.

        Returns:
            Tuple of response headers and JSON payload.
        """
        return self._github.requester.graphql_query(
            query=query,
            variables=variables,
        )
