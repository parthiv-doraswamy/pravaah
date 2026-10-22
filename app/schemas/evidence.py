"""Contracts for application evidence metadata and expiry tracking."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    title: str = Field(min_length=2, max_length=240, strip_whitespace=True)
    category: str = Field(min_length=2, max_length=80, strip_whitespace=True)
    reference_number: str | None = Field(default=None, max_length=160, strip_whitespace=True)
    issued_on: date | None = None
    expires_on: date | None = None
    policy_key: str | None = Field(default=None, max_length=100, strip_whitespace=True)
    notes: str | None = Field(default=None, max_length=3000)


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    title: str
    category: str
    reference_number: str | None
    issued_on: date | None
    expires_on: date | None
    policy_key: str | None
    notes: str | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
