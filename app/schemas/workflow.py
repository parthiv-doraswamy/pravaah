"""Contracts for workflow transitions, policy versions, and case history."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TransitionRequest(BaseModel):
    target_status: str = Field(min_length=3, max_length=60)
    expected_status: str = Field(min_length=3, max_length=60)
    reason: str | None = Field(default=None, max_length=2000)


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    sequence: int
    event_type: str
    from_status: str | None
    to_status: str | None
    actor_user_id: UUID | None
    reason: str | None
    event_metadata: dict
    occurred_at: datetime
    previous_hash: str
    event_hash: str


class EventChainVerification(BaseModel):
    application_id: UUID
    valid: bool
    event_count: int
    first_invalid_sequence: int | None


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    policy_key: str
    version: int
    title: str
    description: str
    effective_from: datetime
    rules: dict
    rules_schema_version: int
    source_label: str
    is_active: bool
    created_at: datetime
