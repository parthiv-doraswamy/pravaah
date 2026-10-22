"""Request and response contracts for the application registry."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240, strip_whitespace=True)
    summary: str | None = Field(default=None, max_length=5000)


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_number: str
    title: str
    status: str
    summary: str | None
    institution_id: UUID
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    items: list[ApplicationResponse]
    page: int
    page_size: int
    total: int
