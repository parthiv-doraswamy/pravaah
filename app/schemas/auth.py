"""Schemas for login and current-user responses.

Synthetic demo identities intentionally use the reserved .test domain, so these
contracts validate email shape without requiring a publicly deliverable domain.
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320, pattern=_EMAIL_PATTERN)
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    institution_id: UUID | None
