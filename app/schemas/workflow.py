"""Contracts for workflow transitions, policy versions, and case history."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class PolicyCreate(BaseModel):
    """Create a new immutable policy version; activation is a separate reviewed action."""

    policy_key: str = Field(min_length=2, max_length=100, pattern=r"^[a-z][a-z0-9_.-]*$")
    version: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=240)
    description: str = Field(min_length=1, max_length=5000)
    effective_from: datetime
    rules: dict
    rules_schema_version: int = Field(default=1, ge=1)
    source_label: str = Field(default="PRAVAAH synthetic demo policy", min_length=3, max_length=240)

    @field_validator("effective_from")
    @classmethod
    def effective_from_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("effective_from must include a timezone")
        return value


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
