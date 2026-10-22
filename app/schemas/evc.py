"""Request and response schemas for EVC visit scheduling."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EVCVisitCreate(BaseModel):
    application_id: UUID
    scheduled_for: datetime
    mode: Literal["onsite", "virtual"] = "onsite"
    location: str | None = Field(default=None, max_length=240)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("scheduled_for")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_for must include a timezone offset")
        return value


class EVCVisitStatusUpdate(BaseModel):
    status: Literal["completed", "cancelled"]


class EVCVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    scheduled_for: datetime
    mode: str
    location: str | None
    notes: str | None
    status: str
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
