"""Contracts for application evidence metadata and expiry tracking."""

from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


EvidenceTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=240)]
EvidenceCategory = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
EvidenceReference = Annotated[str, StringConstraints(strip_whitespace=True, max_length=160)]
EvidencePolicyKey = Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]


class EvidenceCreate(BaseModel):
    title: EvidenceTitle
    category: EvidenceCategory
    reference_number: EvidenceReference | None = None
    issued_on: date | None = None
    expires_on: date | None = None
    policy_key: EvidencePolicyKey | None = None
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


class EvidenceAttachmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    evidence_id: UUID
    original_filename: str
    content_type: str
    size_bytes: int
    sha256_hex: str
    uploaded_by_user_id: UUID | None
    created_at: datetime
