"""Pydantic schemas for local Git workspace state."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceInfo(BaseModel):
    """Snapshot of a prepared local Git workspace."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository_name: str
    local_path: str
    current_branch: str
    default_branch: str
    feature_branch: str | None = None
    is_clean: bool
    has_uncommitted_changes: bool
    last_commit: str | None = Field(
        default=None,
        description="Short SHA of HEAD, when available",
    )
    remote_url: str | None = None
