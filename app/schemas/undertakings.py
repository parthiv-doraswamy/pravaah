"""Request and response contracts for compliance submission review."""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SubmissionType = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
SubmissionTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]
DeclarationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=20, max_length=10000)]

class ComplianceSubmissionCreate(BaseModel):
    submission_type: SubmissionType
    title: SubmissionTitle
    declaration: DeclarationText
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)

class ComplianceSubmissionReview(BaseModel):
    decision: Literal["accepted", "changes_requested", "rejected"]
    notes: str | None = Field(default=None, max_length=3000)

class ComplianceSubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    application_id: UUID
    submission_type: str
    title: str
    declaration: str
    evidence_ids: list[UUID]
    status: str
    version: int
    submitted_by_user_id: UUID | None
    submitted_at: datetime | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    review_notes: str | None
    supersedes_submission_id: UUID | None
    created_at: datetime
    updated_at: datetime
