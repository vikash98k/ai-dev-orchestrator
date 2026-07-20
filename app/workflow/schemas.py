"""Pydantic schemas for the workflow decision layer."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkflowCandidate(BaseModel):
    """An issue under consideration for execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_number: int
    title: str
    priority: str | None = None
    status: str | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    milestone: str | None = None
    created_at: datetime | None = None
    score: float = 0.0


class SelectedTask(BaseModel):
    """The single task chosen by the workflow engine (decision only)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_number: int
    title: str
    selection_reason: str
    branch_name: str = Field(description="Predicted branch name; not created")
    estimated_priority: str | None = None
    score: float = 0.0
    ticket_id: str | None = None


class WorkflowScanResult(BaseModel):
    """Aggregate scan output for CLI / future orchestrators."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: str
    total_issues: int
    ready_count: int
    eligible_count: int
    selected: SelectedTask | None = None
    candidates: list[WorkflowCandidate] = Field(default_factory=list)
