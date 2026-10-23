"""API contracts for the in-app notification center."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    evidence_id: UUID | None
    notification_type: str
    title: str
    message: str
    severity: str
    delivery_status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None
    last_error: str | None
    created_at: datetime
    read_at: datetime | None
    sent_at: datetime | None


class NotificationQueueResult(BaseModel):
    as_of: datetime
    created: int
    skipped_existing: int
    recipient_count: int
    detail: str


class NotificationOperationsItem(BaseModel):
    id: UUID
    application_id: UUID
    application_number: str
    application_title: str
    recipient_name: str
    recipient_role: str
    notification_type: str
    title: str
    message: str
    severity: str
    delivery_status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    read_at: datetime | None
    sent_at: datetime | None


class NotificationOperationsSummary(BaseModel):
    as_of: datetime
    total: int
    by_status: dict[str, int]
    failed: int
    retry_ready: int
    exhausted: int
    items: list[NotificationOperationsItem]
