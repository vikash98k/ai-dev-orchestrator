"""Reusable issue manager for read-only GitHub issue access.

Depends on :class:`~app.github.repository_manager.RepositoryManager` for
repository lookup so repository access logic is never duplicated. This module
is intended as the issue source of truth for the future workflow engine.
"""

from __future__ import annotations

import logging
from typing import Any

from github import (
    GithubException,
    RateLimitExceededException,
    UnknownObjectException,
)
from github.Issue import Issue
from github.Repository import Repository
from requests.exceptions import RequestException

from app.github.exceptions import (
    GitHubAPIError,
    IssueAccessDeniedError,
    IssueNotFoundError,
    IssueValidationError,
    RateLimitExceededError,
)
from app.github.repository_manager import RepositoryManager
from app.github.schemas import IssueDetail, IssueSummary

logger = logging.getLogger(__name__)


class IssueManager:
    """Read and filter GitHub issues for a repository.

    Responsibilities:
        - List issues (all / open / closed)
        - Fetch a single issue as :class:`IssueDetail`
        - Filter by label, assignee, or keyword
        - Return strongly typed Pydantic models

    Example:
        >>> issues = IssueManager(repository_manager)
        >>> open_issues = issues.list_open_issues("vikash98k", "fashion-store-backend")
    """

    def __init__(self, repository_manager: RepositoryManager) -> None:
        """Initialize with an injected repository manager.

        Args:
            repository_manager: Provides authenticated repository access.
        """
        self._repository_manager = repository_manager
        logger.debug("IssueManager initialized")

    def list_issues(self, owner: str, repo: str) -> list[IssueSummary]:
        """Return all issues for a repository (excluding pull requests).

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            Issue summaries for every non-PR issue.
        """
        return self._list_issue_summaries(owner, repo, state="all")

    def list_open_issues(self, owner: str, repo: str) -> list[IssueSummary]:
        """Return open issues for a repository.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            Summaries for open, non-PR issues.
        """
        return self._list_issue_summaries(owner, repo, state="open")

    def list_closed_issues(self, owner: str, repo: str) -> list[IssueSummary]:
        """Return closed issues for a repository.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.

        Returns:
            Summaries for closed, non-PR issues.
        """
        return self._list_issue_summaries(owner, repo, state="closed")

    def get_issue(self, owner: str, repo: str, issue_number: int) -> IssueDetail:
        """Fetch a single issue by number.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.
            issue_number: Issue number (must be a positive integer).

        Returns:
            Full :class:`IssueDetail` for the requested issue.

        Raises:
            IssueValidationError: If ``issue_number`` is invalid.
            IssueNotFoundError: If the issue does not exist.
            IssueAccessDeniedError: If the token cannot access the issue.
            RateLimitExceededError: If the API rate limit is exceeded.
            GitHubAPIError: For unexpected or transient API failures.
        """
        if not isinstance(issue_number, int) or isinstance(issue_number, bool):
            raise IssueValidationError("Issue number must be an integer.")
        if issue_number <= 0:
            raise IssueValidationError("Issue number must be a positive integer.")

        repository = self._repository_manager.get_repository(owner, repo)
        full_name = f"{owner}/{repo}"
        logger.info(
            "Loading issue",
            extra={"repository": full_name, "issue_number": issue_number},
        )

        try:
            issue = repository.get_issue(issue_number)
        except (
            UnknownObjectException,
            RateLimitExceededException,
            GithubException,
            RequestException,
        ) as exc:
            self._raise_for_issue_error(exc, full_name, issue_number=issue_number)

        detail = IssueDetail.from_issue(issue)
        logger.info(
            "Issue loaded",
            extra={
                "repository": full_name,
                "issue_number": detail.number,
                "state": detail.state,
            },
        )
        return detail

    def list_issues_by_label(
        self,
        owner: str,
        repo: str,
        label: str,
    ) -> list[IssueSummary]:
        """Return issues that carry a specific label.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.
            label: Exact label name to match.

        Returns:
            Matching issue summaries.

        Raises:
            IssueValidationError: If ``label`` is blank.
        """
        normalized = self._require_non_empty(label, "label")
        logger.info(
            "Filtering issues",
            extra={"repository": f"{owner}/{repo}", "label": normalized},
        )
        return self._list_issue_summaries(
            owner,
            repo,
            state="all",
            labels=[normalized],
        )

    def list_issues_by_assignee(
        self,
        owner: str,
        repo: str,
        assignee: str,
    ) -> list[IssueSummary]:
        """Return issues assigned to a specific user.

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.
            assignee: GitHub login of the assignee.

        Returns:
            Matching issue summaries.

        Raises:
            IssueValidationError: If ``assignee`` is blank.
        """
        normalized = self._require_non_empty(assignee, "assignee")
        logger.info(
            "Filtering issues",
            extra={"repository": f"{owner}/{repo}", "assignee": normalized},
        )
        return self._list_issue_summaries(
            owner,
            repo,
            state="all",
            assignee=normalized,
        )

    def search_issues(
        self,
        owner: str,
        repo: str,
        keyword: str,
    ) -> list[IssueSummary]:
        """Search issues whose title or body contains a keyword.

        Matching is case-insensitive and performed against fetched issues
        (read-only; no GitHub search API side effects).

        Args:
            owner: GitHub user or organization login.
            repo: Repository name.
            keyword: Substring to look for in title or body.

        Returns:
            Matching issue summaries.

        Raises:
            IssueValidationError: If ``keyword`` is blank.
        """
        normalized = self._require_non_empty(keyword, "keyword").lower()
        logger.info(
            "Filtering issues",
            extra={"repository": f"{owner}/{repo}", "keyword": normalized},
        )

        repository = self._repository_manager.get_repository(owner, repo)
        issues = self._fetch_issues(repository, owner, repo, state="all")
        matches: list[IssueSummary] = []
        for issue in issues:
            if issue.pull_request is not None:
                continue
            title = (issue.title or "").lower()
            body = (issue.body or "").lower()
            if normalized in title or normalized in body:
                matches.append(IssueSummary.from_issue(issue))
        return matches

    def _list_issue_summaries(
        self,
        owner: str,
        repo: str,
        *,
        state: str,
        labels: list[str] | None = None,
        assignee: str | None = None,
    ) -> list[IssueSummary]:
        """Shared list path that maps PyGithub issues to summaries."""
        repository = self._repository_manager.get_repository(owner, repo)
        raw_issues = self._fetch_issues(
            repository,
            owner,
            repo,
            state=state,
            labels=labels,
            assignee=assignee,
        )
        summaries = [
            IssueSummary.from_issue(issue)
            for issue in raw_issues
            if issue.pull_request is None
        ]
        logger.info(
            "Issues loaded",
            extra={
                "repository": f"{owner}/{repo}",
                "state": state,
                "count": len(summaries),
            },
        )
        return summaries

    def _fetch_issues(
        self,
        repository: Repository,
        owner: str,
        repo: str,
        *,
        state: str,
        labels: list[str] | None = None,
        assignee: str | None = None,
    ) -> list[Issue]:
        """Fetch issues from GitHub and translate API failures."""
        full_name = f"{owner}/{repo}"
        logger.info(
            "Loading issues",
            extra={
                "repository": full_name,
                "state": state,
                "labels": labels,
                "assignee": assignee,
            },
        )
        kwargs: dict[str, Any] = {"state": state}
        if labels is not None:
            kwargs["labels"] = labels
        if assignee is not None:
            kwargs["assignee"] = assignee

        try:
            return list(repository.get_issues(**kwargs))
        except (
            UnknownObjectException,
            RateLimitExceededException,
            GithubException,
            RequestException,
        ) as exc:
            self._raise_for_issue_error(exc, full_name)
            raise  # pragma: no cover

    @staticmethod
    def _require_non_empty(value: str, field_name: str) -> str:
        """Validate and normalize a required string filter value."""
        if not isinstance(value, str) or not value.strip():
            raise IssueValidationError(f"{field_name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _raise_for_issue_error(
        exc: BaseException,
        full_name: str,
        *,
        issue_number: int | None = None,
    ) -> None:
        """Translate PyGithub / network errors into issue domain exceptions."""
        target = (
            f"{full_name}#{issue_number}" if issue_number is not None else full_name
        )

        if isinstance(exc, UnknownObjectException):
            logger.error(
                "Issue not found",
                extra={"target": target, "status": exc.status},
            )
            raise IssueNotFoundError(f"Issue '{target}' was not found.") from exc

        if isinstance(exc, RateLimitExceededException):
            logger.error(
                "GitHub API failures",
                extra={"target": target, "status": exc.status, "kind": "rate_limit"},
            )
            raise RateLimitExceededError(
                f"GitHub API rate limit exceeded while accessing issues for '{target}'."
            ) from exc

        if isinstance(exc, GithubException):
            status = exc.status
            if status == 404:
                logger.error(
                    "Issue not found",
                    extra={"target": target, "status": status},
                )
                raise IssueNotFoundError(f"Issue '{target}' was not found.") from exc
            if status in {401, 403}:
                logger.error(
                    "GitHub API failures",
                    extra={"target": target, "status": status, "kind": "permission"},
                )
                raise IssueAccessDeniedError(
                    f"Access denied for issues on '{target}' "
                    f"(status={status}). Check token permissions."
                ) from exc
            logger.error(
                "GitHub API failures",
                extra={"target": target, "status": status, "detail": str(exc)},
            )
            raise GitHubAPIError(
                f"Unexpected GitHub API error for issues on '{target}' "
                f"(status={status}): {exc.data}"
            ) from exc

        if isinstance(exc, RequestException):
            logger.error(
                "GitHub API failures",
                extra={"target": target, "detail": str(exc), "kind": "network"},
            )
            raise GitHubAPIError(
                f"Network failure while accessing issues for '{target}': {exc}"
            ) from exc

        raise AssertionError(
            f"Unhandled exception type passed to _raise_for_issue_error: {type(exc)!r}"
        )
