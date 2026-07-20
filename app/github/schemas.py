"""Pydantic schemas for GitHub repository and issue metadata.

These models are the stable contract between the infrastructure layer and
future application services (issues, PRs, branches, workflows).
"""

from __future__ import annotations

from datetime import datetime

from github.Issue import Issue
from github.Repository import Repository
from pydantic import BaseModel, ConfigDict, Field


class RepositoryInfo(BaseModel):
    """Strongly typed metadata for a GitHub repository.

    Built from a PyGithub ``Repository`` via :meth:`from_repository` so callers
    never depend on PyGithub attribute shapes.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(description="Repository name")
    owner: str = Field(description="Owner login (user or organization)")
    description: str | None = Field(default=None, description="Repository description")
    visibility: str = Field(description="public, private, or internal")
    private: bool = Field(description="Whether the repository is private")
    default_branch: str = Field(description="Default branch name")
    stars: int = Field(description="Stargazers count")
    forks: int = Field(description="Forks count")
    open_issues_count: int = Field(description="Open issues count")
    language: str | None = Field(default=None, description="Primary language")
    license: str | None = Field(
        default=None,
        description="SPDX license identifier when available",
    )
    created_at: datetime = Field(description="Repository creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    clone_url: str = Field(description="HTTPS clone URL")
    ssh_url: str = Field(description="SSH clone URL")
    html_url: str = Field(description="GitHub web URL")
    size: int = Field(description="Repository size in kilobytes")
    archived: bool = Field(description="Whether the repository is archived")
    disabled: bool = Field(description="Whether the repository is disabled")
    topics: list[str] = Field(
        default_factory=list,
        description="Repository topic labels",
    )

    @classmethod
    def from_repository(cls, repository: Repository) -> RepositoryInfo:
        """Map a PyGithub ``Repository`` into a validated schema instance.

        Args:
            repository: Authenticated PyGithub repository object.

        Returns:
            Immutable :class:`RepositoryInfo` populated from the API object.
        """
        license_id: str | None = None
        if repository.license is not None:
            license_id = repository.license.spdx_id or repository.license.name

        topics = list(repository.get_topics())

        return cls(
            name=repository.name,
            owner=repository.owner.login,
            description=repository.description,
            visibility=repository.visibility,
            private=repository.private,
            default_branch=repository.default_branch,
            stars=repository.stargazers_count,
            forks=repository.forks_count,
            open_issues_count=repository.open_issues_count,
            language=repository.language,
            license=license_id,
            created_at=repository.created_at,
            updated_at=repository.updated_at,
            clone_url=repository.clone_url,
            ssh_url=repository.ssh_url,
            html_url=repository.html_url,
            size=repository.size,
            archived=repository.archived,
            disabled=repository.disabled,
            topics=topics,
        )


class IssueSummary(BaseModel):
    """Lightweight issue representation for lists and filters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int = Field(description="Issue number")
    title: str = Field(description="Issue title")
    state: str = Field(description="open or closed")
    labels: list[str] = Field(default_factory=list, description="Label names")
    assignees: list[str] = Field(
        default_factory=list,
        description="Assignee logins",
    )
    milestone: str | None = Field(default=None, description="Milestone title")
    author: str = Field(description="Author login")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    url: str = Field(description="GitHub HTML URL")

    @classmethod
    def from_issue(cls, issue: Issue) -> IssueSummary:
        """Map a PyGithub ``Issue`` into an :class:`IssueSummary`.

        Args:
            issue: Authenticated PyGithub issue object.

        Returns:
            Immutable summary model.
        """
        return cls(
            number=issue.number,
            title=issue.title,
            state=issue.state,
            labels=[label.name for label in issue.labels],
            assignees=[user.login for user in issue.assignees],
            milestone=issue.milestone.title if issue.milestone else None,
            author=issue.user.login if issue.user else "unknown",
            created_at=issue.created_at,
            updated_at=issue.updated_at,
            url=issue.html_url,
        )


class IssueDetail(IssueSummary):
    """Full issue representation including body and pull-request flag."""

    body: str | None = Field(default=None, description="Issue body markdown")
    comments_count: int = Field(description="Comment count")
    is_pull_request: bool = Field(
        description="True when the GitHub issue item is a pull request",
    )

    @classmethod
    def from_issue(cls, issue: Issue) -> IssueDetail:
        """Map a PyGithub ``Issue`` into an :class:`IssueDetail`.

        Args:
            issue: Authenticated PyGithub issue object.

        Returns:
            Immutable detail model.
        """
        summary = IssueSummary.from_issue(issue)
        return cls(
            **summary.model_dump(),
            body=issue.body,
            comments_count=issue.comments,
            is_pull_request=issue.pull_request is not None,
        )


class ProjectInfo(BaseModel):
    """Metadata for a GitHub Project V2 board."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Project node ID")
    title: str = Field(description="Project title")
    number: int = Field(description="Project number")
    owner: str = Field(description="Owner login")
    url: str = Field(description="Project URL")


class ProjectItem(BaseModel):
    """A Project V2 item linked to an issue, with workflow fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_number: int = Field(description="Linked issue number")
    issue_title: str = Field(description="Linked issue title")
    status: str | None = Field(default=None, description="Status field value")
    labels: list[str] = Field(default_factory=list, description="Issue labels")
    assignees: list[str] = Field(default_factory=list, description="Assignee logins")
    milestone: str | None = Field(default=None, description="Milestone title")
    priority: str | None = Field(default=None, description="Priority field value")
    iteration: str | None = Field(default=None, description="Iteration field value")
    created_at: datetime | None = Field(
        default=None,
        description="Issue creation timestamp",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Issue last update timestamp",
    )


class ProjectBoard(BaseModel):
    """Full project board snapshot for workflow consumption."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project: ProjectInfo = Field(description="Project metadata")
    items: list[ProjectItem] = Field(default_factory=list, description="Board items")
    total_items: int = Field(description="Total item count")
