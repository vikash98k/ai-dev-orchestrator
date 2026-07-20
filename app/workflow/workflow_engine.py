"""Workflow engine — decision layer for selecting the next task.

Depends on GitHub managers via dependency injection and never calls the
GitHub API directly. It does not create branches, update issues, or run AI.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection

from app.github.issue_manager import IssueManager
from app.github.project_manager import ProjectBoardManager
from app.github.repository_manager import RepositoryManager
from app.github.schemas import ProjectItem
from app.workflow.exceptions import (
    NoEligibleTaskError,
    TaskSelectionError,
)
from app.workflow.rules import (
    DEFAULT_AI_AGENT_ASSIGNEES,
    DEFAULT_ARCHIVED_LABELS,
    DEFAULT_DRAFT_LABELS,
    DEFAULT_LOCKED_LABELS,
    DEFAULT_READY_STATUSES,
    candidate_from_item_and_issue,
    is_eligible,
    is_ready,
)
from app.workflow.schemas import (
    SelectedTask,
    WorkflowCandidate,
    WorkflowScanResult,
)
from app.workflow.selectors import CompositeSelector, TaskSelector, default_selector

logger = logging.getLogger(__name__)

_TICKET_RE = re.compile(r"^([A-Z][A-Z0-9]+-\d+)\b")
_NON_SLUG_RE = re.compile(r"[^a-z0-9]+")


class WorkflowEngine:
    """Select the single best eligible task from a Project V2 board.

    Responsibilities:
        - Load project items and issue details through injected managers
        - Apply eligibility rules
        - Rank candidates with pluggable selectors
        - Predict a branch name (never create it)

    Example:
        >>> engine = WorkflowEngine(repositories, issues, projects)
        >>> result = engine.scan_and_select("vikash98k", "fashion-store-backend", 6)
        >>> print(result.selected.branch_name)
    """

    def __init__(
        self,
        repository_manager: RepositoryManager,
        issue_manager: IssueManager,
        project_manager: ProjectBoardManager,
        *,
        selector: TaskSelector | None = None,
        ready_statuses: Collection[str] = DEFAULT_READY_STATUSES,
        locked_labels: Collection[str] = DEFAULT_LOCKED_LABELS,
        draft_labels: Collection[str] = DEFAULT_DRAFT_LABELS,
        archived_labels: Collection[str] = DEFAULT_ARCHIVED_LABELS,
        ai_agent_assignees: Collection[str] = DEFAULT_AI_AGENT_ASSIGNEES,
    ) -> None:
        """Initialize the engine with managers and optional rule overrides.

        Args:
            repository_manager: Repository access (validation / future hooks).
            issue_manager: Issue read access.
            project_manager: Project board read access.
            selector: Scoring strategy (defaults to Priority+Oldest+FIFO).
            ready_statuses: Allowed Ready status names.
            locked_labels: Labels that mark a task locked.
            draft_labels: Labels that mark a draft.
            archived_labels: Labels that mark archived work.
            ai_agent_assignees: Logins treated as AI agents.
        """
        self._repositories = repository_manager
        self._issues = issue_manager
        self._projects = project_manager
        self._selector = selector or default_selector()
        self._ready_statuses = frozenset(ready_statuses)
        self._locked_labels = frozenset(locked_labels)
        self._draft_labels = frozenset(draft_labels)
        self._archived_labels = frozenset(archived_labels)
        self._ai_agent_assignees = frozenset(ai_agent_assignees)
        logger.debug("WorkflowEngine initialized")

    def scan_and_select(
        self,
        owner: str,
        repo: str,
        project_number: int,
    ) -> WorkflowScanResult:
        """Scan the board and select the next eligible task.

        Args:
            owner: GitHub owner login.
            repo: Repository name.
            project_number: Project V2 number.

        Returns:
            :class:`WorkflowScanResult` including counts and selected task.

        Raises:
            NoEligibleTaskError: When nothing is eligible.
            TaskSelectionError: On unexpected selection failures.
        """
        # Touch repository manager so invalid repos fail early without
        # duplicating lookup logic inside the workflow layer.
        self._repositories.get_repository(owner, repo)

        logger.info(
            "Loading project items",
            extra={"owner": owner, "repo": repo, "project_number": project_number},
        )
        board = self._projects.get_board(owner, project_number)
        open_issues = self._issues.list_open_issues(owner, repo)
        total_issues = len(open_issues)

        ready_items = [
            item
            for item in board.items
            if is_ready(item, ready_statuses=self._ready_statuses)
        ]
        logger.info(
            "Loading project items",
            extra={
                "total_items": board.total_items,
                "ready_count": len(ready_items),
                "open_issues": total_issues,
            },
        )

        eligible: list[WorkflowCandidate] = []
        for item in ready_items:
            candidate = self._evaluate_item(owner, repo, item)
            if candidate is not None:
                eligible.append(candidate)

        if not eligible:
            raise NoEligibleTaskError(
                f"No eligible Ready tasks found for {owner}/{repo} "
                f"on project #{project_number}."
            )

        try:
            selected_candidate = max(eligible, key=lambda item: item.score)
        except ValueError as exc:
            raise TaskSelectionError(
                f"Failed to select a task for {owner}/{repo}: {exc}"
            ) from exc

        selected = self._to_selected_task(selected_candidate)
        logger.info(
            "Issue selected",
            extra={
                "issue_number": selected.issue_number,
                "score": selected.score,
                "branch_name": selected.branch_name,
            },
        )
        return WorkflowScanResult(
            repository=repo,
            total_issues=total_issues,
            ready_count=len(ready_items),
            eligible_count=len(eligible),
            selected=selected,
            candidates=eligible,
        )

    def select_next_task(
        self,
        owner: str,
        repo: str,
        project_number: int,
    ) -> SelectedTask:
        """Return only the selected task (raises if none eligible)."""
        result = self.scan_and_select(owner, repo, project_number)
        if result.selected is None:
            raise NoEligibleTaskError("Selection returned no task.")
        return result.selected

    def _evaluate_item(
        self,
        owner: str,
        repo: str,
        item: ProjectItem,
    ) -> WorkflowCandidate | None:
        """Load issue details, apply rules, and score an eligible candidate."""
        logger.info(
            "Evaluating issue",
            extra={"issue_number": item.issue_number, "title": item.issue_title},
        )
        issue = self._issues.get_issue(owner, repo, item.issue_number)
        eligible, reason = is_eligible(
            item,
            issue,
            ready_statuses=self._ready_statuses,
            locked_labels=self._locked_labels,
            draft_labels=self._draft_labels,
            archived_labels=self._archived_labels,
            ai_agent_assignees=self._ai_agent_assignees,
        )
        if not eligible:
            logger.info(
                "Issue skipped",
                extra={"issue_number": item.issue_number, "reason": reason},
            )
            return None

        candidate = candidate_from_item_and_issue(item, issue)
        score = float(self._selector.score(candidate))
        scored = candidate.model_copy(update={"score": score})
        logger.info(
            "Issue accepted",
            extra={"issue_number": scored.issue_number, "score": scored.score},
        )
        logger.info(
            "Selection score",
            extra={"issue_number": scored.issue_number, "score": scored.score},
        )
        return scored

    def _to_selected_task(self, candidate: WorkflowCandidate) -> SelectedTask:
        """Map a scored candidate into a :class:`SelectedTask`."""
        ticket_id = extract_ticket_id(candidate.title, candidate.issue_number)
        branch_name = predict_branch_name(candidate.title, candidate.issue_number)
        if isinstance(self._selector, CompositeSelector):
            reason = self._selector.reason_for(candidate)
        else:
            reason = self._selector.name
        return SelectedTask(
            issue_number=candidate.issue_number,
            title=candidate.title,
            selection_reason=reason,
            branch_name=branch_name,
            estimated_priority=candidate.priority,
            score=round(candidate.score, 2),
            ticket_id=ticket_id,
        )


def extract_ticket_id(title: str, issue_number: int) -> str:
    """Extract ``AUTH-001``-style id from the title, else ``ISSUE-<n>``."""
    match = _TICKET_RE.match(title.strip())
    if match:
        return match.group(1)
    return f"ISSUE-{issue_number}"


def predict_branch_name(title: str, issue_number: int) -> str:
    """Predict a feature branch name without creating it.

    Examples:
        ``Create User Entity`` → ``feature/issue-12-create-user-entity``
        ``AUTH-001 Create User Entity`` → ``feature/auth-001-create-user-entity``
    """
    ticket = extract_ticket_id(title, issue_number).lower()
    remainder = title.strip()
    match = _TICKET_RE.match(remainder)
    if match:
        remainder = remainder[match.end() :].lstrip(" :-")
    slug = _NON_SLUG_RE.sub("-", remainder.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "task"
    # Keep branch names reasonably short for GitHub.
    slug = "-".join(slug.split("-")[:6])
    return f"feature/{ticket}-{slug}"
