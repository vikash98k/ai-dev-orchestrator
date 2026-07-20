"""Pydantic schemas for GitHub repository metadata.

These models are the stable contract between the infrastructure layer and
future application services (issues, PRs, branches, workflows).
"""

from __future__ import annotations

from datetime import datetime

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
