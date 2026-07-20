"""Custom exceptions for the workflow decision layer."""


class WorkflowError(Exception):
    """Base exception for workflow engine failures."""


class WorkflowConfigurationError(WorkflowError):
    """Raised when workflow configuration is invalid."""


class NoEligibleTaskError(WorkflowError):
    """Raised when no project item satisfies eligibility rules."""


class TaskSelectionError(WorkflowError):
    """Raised when task selection fails unexpectedly."""
