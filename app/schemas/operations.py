"""Response contracts for scoped operations intelligence."""

from datetime import date
from pydantic import BaseModel, Field


class OperationsMetrics(BaseModel):
    """Role-scoped aggregate metrics derived from persisted workflow records."""

    as_of: date
    total_applications: int = Field(ge=0)
    active_applications: int = Field(ge=0)
    awaiting_review: int = Field(ge=0)
    completed_applications: int = Field(ge=0)
    applications_by_status: dict[str, int]
    submissions_pending_review: int = Field(ge=0)
    expired_evidence: int = Field(ge=0)
    evidence_due_within_7_days: int = Field(ge=0)
    open_escalations: int = Field(ge=0)
    failed_notifications: int = Field(ge=0)
    evc_reports_pending: int = Field(ge=0)


class PendencyItem(BaseModel):
    """A visible application currently waiting for workflow action."""

    application_id: str
    application_number: str
    title: str
    status: str
    institution_name: str
    waiting_since: date
    days_waiting: int = Field(ge=0)


class PendencyStatusSummary(BaseModel):
    """Aggregated wait-time statistics for a workflow status."""

    status: str
    count: int = Field(ge=0)
    oldest_days: int = Field(ge=0)
    average_days: float = Field(ge=0)


class PendencyAnalytics(BaseModel):
    """Scoped pendency aging and workload summary."""

    as_of: date
    total_pending: int = Field(ge=0)
    aging_buckets: dict[str, int]
    by_status: list[PendencyStatusSummary]
    oldest_items: list[PendencyItem]


class TaskInboxItem(BaseModel):
    """A role-relevant task derived from persisted workflow records."""

    task_id: str
    task_type: str
    title: str
    description: str
    priority: str = Field(pattern="^(high|medium|low)$")
    status: str
    application_id: str
    application_number: str
    application_title: str
    institution_name: str
    created_at: date
    due_date: date | None = None
    action_view: str = Field(pattern="^(applications|detail|compliance|evc|notifications)$")


class TaskInbox(BaseModel):
    """Unified, role-scoped task list and counts."""

    as_of: date
    total: int = Field(ge=0)
    by_priority: dict[str, int]
    by_type: dict[str, int]
    items: list[TaskInboxItem]
