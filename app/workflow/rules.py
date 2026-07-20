"""Eligibility rules for workflow task selection.

Rules are pure functions so they stay easy to unit-test and extend
(AI assignment, blockers, story points, etc. later).
"""

from __future__ import annotations

from collections.abc import Collection

from app.github.schemas import IssueDetail, ProjectItem
from app.workflow.schemas import WorkflowCandidate

# Configurable defaults — override via WorkflowEngine constructor, not hardcoding
# call sites throughout the app.
DEFAULT_READY_STATUSES: frozenset[str] = frozenset({"ready"})
DEFAULT_LOCKED_LABELS: frozenset[str] = frozenset({"locked", "on-hold", "blocked"})
DEFAULT_DRAFT_LABELS: frozenset[str] = frozenset({"draft", "wip"})
DEFAULT_ARCHIVED_LABELS: frozenset[str] = frozenset({"archived"})
# Logins treated as AI agents — unassigned humans are fine; other agents block.
DEFAULT_AI_AGENT_ASSIGNEES: frozenset[str] = frozenset(
    {
        "ai-dev-orchestrator",
        "ai-orchestrator",
        "github-actions[bot]",
        "dependabot[bot]",
    }
)


def _normalize(value: str) -> str:
    return value.strip().casefold()


def is_ready(
    item: ProjectItem,
    *,
    ready_statuses: Collection[str] = DEFAULT_READY_STATUSES,
) -> bool:
    """Return True when the project Status field is an allowed Ready value."""
    if item.status is None:
        return False
    allowed = {_normalize(status) for status in ready_statuses}
    return _normalize(item.status) in allowed


def is_open(issue: IssueDetail) -> bool:
    """Return True when the GitHub issue state is open."""
    return _normalize(issue.state) == "open"


def is_locked(
    item: ProjectItem,
    issue: IssueDetail,
    *,
    locked_labels: Collection[str] = DEFAULT_LOCKED_LABELS,
) -> bool:
    """Return True when labels indicate the task is locked / blocked."""
    labels = {_normalize(label) for label in (*item.labels, *issue.labels)}
    blocked = {_normalize(label) for label in locked_labels}
    return bool(labels & blocked)


def is_draft(
    item: ProjectItem,
    issue: IssueDetail,
    *,
    draft_labels: Collection[str] = DEFAULT_DRAFT_LABELS,
) -> bool:
    """Return True when labels indicate a draft / WIP item."""
    labels = {_normalize(label) for label in (*item.labels, *issue.labels)}
    drafts = {_normalize(label) for label in draft_labels}
    return bool(labels & drafts) or issue.is_pull_request


def is_archived(
    item: ProjectItem,
    issue: IssueDetail,
    *,
    archived_labels: Collection[str] = DEFAULT_ARCHIVED_LABELS,
) -> bool:
    """Return True when labels indicate an archived item."""
    labels = {_normalize(label) for label in (*item.labels, *issue.labels)}
    archived = {_normalize(label) for label in archived_labels}
    return bool(labels & archived)


def is_assigned_to_ai_agent(
    item: ProjectItem,
    issue: IssueDetail,
    *,
    ai_agent_assignees: Collection[str] = DEFAULT_AI_AGENT_ASSIGNEES,
) -> bool:
    """Return True when an AI/bot agent already owns the issue.

    Human assignees do not disqualify the task. Only configured agent logins do.
    """
    assignees = {_normalize(login) for login in (*item.assignees, *issue.assignees)}
    agents = {_normalize(login) for login in ai_agent_assignees}
    return bool(assignees & agents)


def is_eligible(
    item: ProjectItem,
    issue: IssueDetail,
    *,
    ready_statuses: Collection[str] = DEFAULT_READY_STATUSES,
    locked_labels: Collection[str] = DEFAULT_LOCKED_LABELS,
    draft_labels: Collection[str] = DEFAULT_DRAFT_LABELS,
    archived_labels: Collection[str] = DEFAULT_ARCHIVED_LABELS,
    ai_agent_assignees: Collection[str] = DEFAULT_AI_AGENT_ASSIGNEES,
) -> tuple[bool, str]:
    """Evaluate full eligibility.

    Returns:
        ``(True, reason)`` when eligible, otherwise ``(False, skip_reason)``.
    """
    if not is_ready(item, ready_statuses=ready_statuses):
        return False, f"status is not Ready ({item.status!r})"
    if not is_open(issue):
        return False, f"issue state is {issue.state!r}"
    if is_assigned_to_ai_agent(
        item,
        issue,
        ai_agent_assignees=ai_agent_assignees,
    ):
        return False, "assigned to another AI agent"
    if is_locked(item, issue, locked_labels=locked_labels):
        return False, "locked or blocked"
    if is_draft(item, issue, draft_labels=draft_labels):
        return False, "draft or pull request"
    if is_archived(item, issue, archived_labels=archived_labels):
        return False, "archived"
    return True, "eligible"


def candidate_from_item_and_issue(
    item: ProjectItem,
    issue: IssueDetail,
    *,
    score: float = 0.0,
) -> WorkflowCandidate:
    """Build a :class:`WorkflowCandidate` from board + issue snapshots."""
    return WorkflowCandidate(
        issue_number=issue.number,
        title=issue.title,
        priority=item.priority,
        status=item.status,
        labels=list(dict.fromkeys([*item.labels, *issue.labels])),
        assignees=list(dict.fromkeys([*item.assignees, *issue.assignees])),
        milestone=item.milestone or issue.milestone,
        created_at=item.created_at or issue.created_at,
        score=score,
    )
