"""Selection strategies for ranking workflow candidates.

Each selector returns an independent score in ``[0, 100]``. A composite
selector combines them with weights so new strategies (team balancing,
story points, dependency graphs) can plug in without changing the engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol

from app.workflow.exceptions import WorkflowConfigurationError
from app.workflow.schemas import WorkflowCandidate

logger = logging.getLogger(__name__)

# Higher rank = preferred. Unknown priorities score as 0.
DEFAULT_PRIORITY_RANKS: dict[str, int] = {
    "critical": 100,
    "urgent": 95,
    "p0": 100,
    "high": 80,
    "p1": 80,
    "medium": 50,
    "normal": 50,
    "p2": 50,
    "low": 20,
    "p3": 20,
}


class TaskSelector(Protocol):
    """Strategy contract for scoring a workflow candidate."""

    @property
    def name(self) -> str:
        """Human-readable strategy name used in selection reasons."""

    def score(self, candidate: WorkflowCandidate) -> float:
        """Return a score in approximately ``[0, 100]``."""


class PriorityFirstSelector:
    """Prefer higher configured priority values."""

    def __init__(self, priority_ranks: dict[str, int] | None = None) -> None:
        self._ranks = {
            key.casefold(): value
            for key, value in (priority_ranks or DEFAULT_PRIORITY_RANKS).items()
        }

    @property
    def name(self) -> str:
        return "Highest Priority"

    def score(self, candidate: WorkflowCandidate) -> float:
        if not candidate.priority:
            return 0.0
        return float(self._ranks.get(candidate.priority.strip().casefold(), 0))


class OldestFirstSelector:
    """Prefer older issues (earlier ``created_at``)."""

    @property
    def name(self) -> str:
        return "Oldest Ready Issue"

    def score(self, candidate: WorkflowCandidate) -> float:
        created = candidate.created_at
        if created is None:
            return 0.0
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        age_days = max((now - created).total_seconds() / 86400.0, 0.0)
        # Cap so extremely old issues don't dominate forever.
        return min(age_days * 2.0, 100.0)


class FIFOSelector:
    """Prefer the lowest issue number (FIFO-ish backlog order)."""

    @property
    def name(self) -> str:
        return "Lowest Issue Number"

    def score(self, candidate: WorkflowCandidate) -> float:
        # Invert issue number into a descending preference within a safe band.
        number = max(candidate.issue_number, 1)
        return max(0.0, 100.0 - min(number, 100))


class PrioritySelector(PriorityFirstSelector):
    """Alias matching the sprint naming."""


class OldestSelector(OldestFirstSelector):
    """Alias matching the sprint naming."""


class RandomSelector:
    """Placeholder for a future randomized exploration strategy."""

    @property
    def name(self) -> str:
        return "Random (placeholder)"

    def score(self, candidate: WorkflowCandidate) -> float:
        logger.debug(
            "RandomSelector is a placeholder and returns a neutral score",
            extra={"issue_number": candidate.issue_number},
        )
        return 0.0


class CompositeSelector:
    """Weighted combination of multiple :class:`TaskSelector` strategies."""

    def __init__(
        self,
        selectors: list[tuple[TaskSelector, float]] | None = None,
    ) -> None:
        """Create a composite selector.

        Args:
            selectors: ``(selector, weight)`` pairs. Weights must be positive.

        Raises:
            WorkflowConfigurationError: If no selectors or invalid weights.
        """
        pairs = selectors or [
            (PriorityFirstSelector(), 0.5),
            (OldestFirstSelector(), 0.3),
            (FIFOSelector(), 0.2),
        ]
        if not pairs:
            raise WorkflowConfigurationError(
                "CompositeSelector requires at least one selector."
            )
        for selector, weight in pairs:
            if weight <= 0:
                raise WorkflowConfigurationError(
                    f"Selector weight for {selector.name!r} must be positive."
                )
        total = sum(weight for _, weight in pairs)
        self._selectors = [(selector, weight / total) for selector, weight in pairs]

    @property
    def name(self) -> str:
        return " + ".join(selector.name for selector, _ in self._selectors)

    def score(self, candidate: WorkflowCandidate) -> float:
        total = 0.0
        for selector, weight in self._selectors:
            part = selector.score(candidate)
            total += part * weight
            logger.debug(
                "Selection score",
                extra={
                    "issue_number": candidate.issue_number,
                    "selector": selector.name,
                    "partial_score": part,
                    "weight": weight,
                },
            )
        return total

    def reason_for(self, candidate: WorkflowCandidate) -> str:
        """Build a human-readable reason from contributing selectors."""
        parts: list[str] = []
        for selector, _weight in self._selectors:
            if selector.score(candidate) > 0:
                parts.append(selector.name)
        return "\n".join(parts) if parts else self.name


def default_selector() -> CompositeSelector:
    """Return the default Priority → Oldest → Lowest-number strategy."""
    return CompositeSelector()
