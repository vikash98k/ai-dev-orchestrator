"""Reusable manager for GitHub Project V2 boards.

Project V2 is GraphQL-only. This manager uses
:meth:`~app.github.client.GitHubClient.execute_graphql` and depends on
:class:`~app.github.repository_manager.RepositoryManager` /
:class:`~app.github.issue_manager.IssueManager` only for architectural
consistency via dependency injection — board reads do not duplicate their
lookup logic.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from app.github.client import GitHubClient
from app.github.exceptions import (
    GitHubAPIError,
    ProjectAccessDeniedError,
    ProjectItemNotFoundError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from app.github.issue_manager import IssueManager
from app.github.repository_manager import RepositoryManager
from app.github.schemas import ProjectBoard, ProjectInfo, ProjectItem

logger = logging.getLogger(__name__)

_PROJECT_USER_QUERY = """
query($login: String!, $number: Int!) {
  user(login: $login) {
    projectV2(number: $number) {
      id
      title
      number
      url
      owner {
        ... on User { login }
        ... on Organization { login }
      }
    }
  }
}
"""

_PROJECT_ORG_QUERY = """
query($login: String!, $number: Int!) {
  organization(login: $login) {
    projectV2(number: $number) {
      id
      title
      number
      url
      owner {
        ... on User { login }
        ... on Organization { login }
      }
    }
  }
}
"""

_PROJECT_ITEMS_QUERY = """
query($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on ProjectV2 {
      items(first: 50, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          content {
            ... on Issue {
              number
              title
              createdAt
              updatedAt
              labels(first: 20) {
                nodes { name }
              }
              assignees(first: 20) {
                nodes { login }
              }
              milestone { title }
            }
          }
          fieldValues(first: 30) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                name
                field {
                  ... on ProjectV2SingleSelectField { name }
                }
              }
              ... on ProjectV2ItemFieldTextValue {
                text
                field {
                  ... on ProjectV2FieldCommon { name }
                }
              }
              ... on ProjectV2ItemFieldIterationValue {
                title
                field {
                  ... on ProjectV2IterationField { name }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


class ProjectBoardManager:
    """Read GitHub Project V2 boards and map issues to workflow status.

    Responsibilities:
        - Load project metadata
        - Load project items and custom fields (Status, Priority, Iteration)
        - Filter items by status
        - Return strongly typed Pydantic models

    Example:
        >>> manager = ProjectBoardManager(client, repositories, issues)
        >>> board = manager.get_board("vikash98k", 1)
        >>> ready = manager.list_ready_items("vikash98k", 1)
    """

    def __init__(
        self,
        github_client: GitHubClient,
        repository_manager: RepositoryManager,
        issue_manager: IssueManager,
    ) -> None:
        """Initialize with injected GitHub collaborators.

        Args:
            github_client: Authenticated client used for GraphQL calls.
            repository_manager: Reserved for future repo-scoped board links.
            issue_manager: Reserved for future issue enrichment without
                duplicating issue-read logic.
        """
        self._github_client = github_client
        self._repository_manager = repository_manager
        self._issue_manager = issue_manager
        logger.debug("ProjectBoardManager initialized")

    def get_project(self, owner: str, project_number: int) -> ProjectInfo:
        """Fetch Project V2 metadata.

        Args:
            owner: User or organization login that owns the project.
            project_number: Project number (visible in the project URL).

        Returns:
            :class:`ProjectInfo` for the board.

        Raises:
            ProjectValidationError: If inputs are invalid.
            ProjectNotFoundError: If the project does not exist.
            ProjectAccessDeniedError: If the token cannot access it.
            GitHubAPIError: For unexpected GraphQL failures.
        """
        login, number = self._validate_owner_and_number(owner, project_number)
        logger.info(
            "Loading project",
            extra={"owner": login, "project_number": number},
        )

        project_node = self._resolve_project_node(login, number)
        info = ProjectInfo(
            id=str(project_node["id"]),
            title=str(project_node["title"]),
            number=int(project_node["number"]),
            owner=str(project_node.get("owner", {}).get("login") or login),
            url=str(project_node["url"]),
        )
        logger.info(
            "Project loaded",
            extra={"owner": info.owner, "project": info.title, "number": info.number},
        )
        return info

    def list_project_items(
        self,
        owner: str,
        project_number: int,
    ) -> list[ProjectItem]:
        """Return all issue-backed items on a project board.

        Draft issues and pull requests without an issue number are skipped.

        Args:
            owner: User or organization login that owns the project.
            project_number: Project number.

        Returns:
            List of :class:`ProjectItem` models.
        """
        project = self.get_project(owner, project_number)
        items = self._fetch_all_items(project)
        logger.info(
            "Project items loaded",
            extra={
                "owner": project.owner,
                "project_number": project.number,
                "count": len(items),
            },
        )
        return items

    def list_items_by_status(
        self,
        owner: str,
        project_number: int,
        status: str,
    ) -> list[ProjectItem]:
        """Return items whose Status field matches ``status``.

        Matching is case-insensitive.

        Args:
            owner: Project owner login.
            project_number: Project number.
            status: Status name (e.g. ``Ready``, ``In Progress``).

        Returns:
            Matching project items.

        Raises:
            ProjectValidationError: If ``status`` is blank.
        """
        if not isinstance(status, str) or not status.strip():
            raise ProjectValidationError("status must be a non-empty string.")
        target = status.strip().casefold()
        logger.info(
            "Status filtering",
            extra={
                "owner": owner,
                "project_number": project_number,
                "status": status.strip(),
            },
        )
        return [
            item
            for item in self.list_project_items(owner, project_number)
            if item.status is not None and item.status.casefold() == target
        ]

    def list_ready_items(
        self,
        owner: str,
        project_number: int,
    ) -> list[ProjectItem]:
        """Return items in the Ready status."""
        return self.list_items_by_status(owner, project_number, "Ready")

    def list_in_progress_items(
        self,
        owner: str,
        project_number: int,
    ) -> list[ProjectItem]:
        """Return items in the In Progress status."""
        return self.list_items_by_status(owner, project_number, "In Progress")

    def get_item(
        self,
        owner: str,
        project_number: int,
        issue_number: int,
    ) -> ProjectItem:
        """Return the project item linked to a specific issue.

        Args:
            owner: Project owner login.
            project_number: Project number.
            issue_number: Issue number on the linked repository.

        Returns:
            Matching :class:`ProjectItem`.

        Raises:
            ProjectValidationError: If ``issue_number`` is invalid.
            ProjectItemNotFoundError: If no matching item exists.
        """
        if not isinstance(issue_number, int) or isinstance(issue_number, bool):
            raise ProjectValidationError("issue_number must be an integer.")
        if issue_number <= 0:
            raise ProjectValidationError("issue_number must be a positive integer.")

        for item in self.list_project_items(owner, project_number):
            if item.issue_number == issue_number:
                return item

        raise ProjectItemNotFoundError(
            f"No project item found for issue #{issue_number} "
            f"on {owner} project #{project_number}."
        )

    def get_board(self, owner: str, project_number: int) -> ProjectBoard:
        """Return a full board snapshot (project + items).

        Args:
            owner: Project owner login.
            project_number: Project number.

        Returns:
            :class:`ProjectBoard` ready for CLI or workflow consumers.
        """
        project = self.get_project(owner, project_number)
        items = self._fetch_all_items(project)
        logger.info(
            "Project items loaded",
            extra={
                "owner": project.owner,
                "project_number": project.number,
                "count": len(items),
            },
        )
        return ProjectBoard(project=project, items=items, total_items=len(items))

    def _fetch_all_items(self, project: ProjectInfo) -> list[ProjectItem]:
        """Paginate all Project V2 items and map issue-backed rows."""
        return [
            mapped
            for raw in self._iter_item_nodes(project)
            if (mapped := self._map_item(raw)) is not None
        ]

    def _iter_item_nodes(self, project: ProjectInfo) -> Iterator[dict[str, Any]]:
        """Yield raw item nodes for a project (pagination only)."""
        cursor: str | None = None
        while True:
            data = self._safe_graphql(
                _PROJECT_ITEMS_QUERY,
                {"id": project.id, "cursor": cursor},
                owner=project.owner,
                project_number=project.number,
            )
            node = data.get("node") or {}
            connection = node.get("items") or {}

            yield from connection.get("nodes") or []

            page_info = connection.get("pageInfo") or {}
            if not page_info.get("hasNextPage"):
                break
            cursor = page_info.get("endCursor")
            if not cursor:
                break

    def _map_item(self, raw: dict[str, Any]) -> ProjectItem | None:
        """Map a GraphQL project item node to :class:`ProjectItem`."""
        content = raw.get("content") or {}
        issue_number = content.get("number")
        issue_title = content.get("title")
        if issue_number is None or issue_title is None:
            return None

        labels = [
            node.get("name")
            for node in (content.get("labels") or {}).get("nodes") or []
            if node.get("name")
        ]
        assignees = [
            node.get("login")
            for node in (content.get("assignees") or {}).get("nodes") or []
            if node.get("login")
        ]
        milestone_node = content.get("milestone") or {}
        milestone = milestone_node.get("title")

        field_map = self._extract_field_values(raw.get("fieldValues") or {})
        return ProjectItem(
            issue_number=int(issue_number),
            issue_title=str(issue_title),
            status=field_map.get("status"),
            labels=[str(label) for label in labels],
            assignees=[str(login) for login in assignees],
            milestone=str(milestone) if milestone else None,
            priority=field_map.get("priority"),
            iteration=field_map.get("iteration"),
            created_at=self._parse_datetime(content.get("createdAt")),
            updated_at=self._parse_datetime(content.get("updatedAt")),
        )

    @staticmethod
    def _extract_field_values(field_values: dict[str, Any]) -> dict[str, str | None]:
        """Pull Status / Priority / Iteration from Project V2 field values."""
        status: str | None = None
        priority: str | None = None
        iteration: str | None = None

        for node in field_values.get("nodes") or []:
            field = node.get("field") or {}
            field_name = (field.get("name") or "").strip().casefold()
            if not field_name:
                continue

            if field_name == "status":
                name = node.get("name")
                if name:
                    status = str(name)
            elif field_name == "priority":
                # Prefer single-select, fall back to text.
                name = node.get("name") or node.get("text")
                if name:
                    priority = str(name)
            elif field_name == "iteration":
                title = node.get("title")
                if title:
                    iteration = str(title)

        return {"status": status, "priority": priority, "iteration": iteration}

    def _resolve_project_node(
        self,
        owner: str,
        project_number: int,
    ) -> dict[str, Any]:
        """Resolve a project from a user login, then an organization login."""
        attempts = (
            (_PROJECT_USER_QUERY, "user"),
            (_PROJECT_ORG_QUERY, "organization"),
        )
        access_denied: ProjectAccessDeniedError | None = None

        for query, key in attempts:
            try:
                data = self._safe_graphql(
                    query,
                    {"login": owner, "number": project_number},
                    owner=owner,
                    project_number=project_number,
                )
            except ProjectAccessDeniedError as exc:
                access_denied = exc
                continue
            except ProjectNotFoundError:
                continue
            except GitHubAPIError as exc:
                message = str(exc).casefold()
                if "could not resolve" in message or "not found" in message:
                    continue
                raise

            container = data.get(key) or {}
            project = container.get("projectV2")
            if isinstance(project, dict) and project.get("id"):
                return project

        if access_denied is not None:
            raise access_denied

        logger.error(
            "Project not found",
            extra={"owner": owner, "project_number": project_number},
        )
        raise ProjectNotFoundError(
            f"Project #{project_number} was not found for '{owner}'."
        )

    def _safe_graphql(
        self,
        query: str,
        variables: dict[str, object],
        *,
        owner: str,
        project_number: int,
    ) -> dict[str, Any]:
        """Execute GraphQL and translate failures into project exceptions."""
        try:
            return self._github_client.execute_graphql(query, variables)
        except GitHubAPIError as exc:
            message = str(exc).casefold()
            if (
                "forbidden" in message
                or "permission" in message
                or "accessible" in message
            ):
                logger.error(
                    "Permission denied",
                    extra={"owner": owner, "project_number": project_number},
                )
                raise ProjectAccessDeniedError(
                    f"Access denied for project #{project_number} owned by "
                    f"'{owner}'. Ensure the token has Projects (read) permission."
                ) from exc
            if "could not resolve" in message or "not found" in message:
                logger.error(
                    "Project not found",
                    extra={"owner": owner, "project_number": project_number},
                )
                raise ProjectNotFoundError(
                    f"Project #{project_number} was not found for '{owner}'."
                ) from exc
            logger.error(
                "Unexpected API failures",
                extra={
                    "owner": owner,
                    "project_number": project_number,
                    "detail": str(exc),
                },
            )
            raise

    @staticmethod
    def _validate_owner_and_number(
        owner: str,
        project_number: int,
    ) -> tuple[str, int]:
        """Validate owner/project_number inputs."""
        if not isinstance(owner, str) or not owner.strip():
            raise ProjectValidationError("owner must be a non-empty string.")
        if not isinstance(project_number, int) or isinstance(project_number, bool):
            raise ProjectValidationError("project_number must be an integer.")
        if project_number <= 0:
            raise ProjectValidationError("project_number must be a positive integer.")
        return owner.strip(), project_number

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        """Parse GraphQL ISO-8601 timestamps into ``datetime``."""
        if not isinstance(value, str) or not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
