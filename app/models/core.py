"""Identity and application registry models.

Passwords are stored only as one-way password hashes; authentication is implemented
in the API security layer. Role and scope checks remain server-side.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


class Institution(Base):
    """Institution account and its regional scope."""

    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    region_code: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="institution")
    applications: Mapped[list["Application"]] = relationship(back_populates="institution")


class User(Base):
    """Application user identity record; role enforcement is added separately."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(60), nullable=False, default="institution_user", index=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    institution: Mapped[Institution | None] = relationship(back_populates="users")


class Application(Base):
    """Approval case registry; transition guards will own status changes."""

    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    application_number: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    status: Mapped[str] = mapped_column(String(60), nullable=False, default="draft", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("institutions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    institution: Mapped[Institution] = relationship(back_populates="applications")
    events: Mapped[list["ApplicationEvent"]] = relationship(back_populates="application", order_by="ApplicationEvent.sequence")
