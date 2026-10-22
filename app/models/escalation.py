"""Escalation records for overdue compliance evidence."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class ComplianceEscalation(Base):
    """An idempotent, auditable escalation raised for long-expired evidence."""

    __tablename__ = "compliance_escalations"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_compliance_escalation_dedupe_key"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dedupe_key: Mapped[str] = mapped_column(String(240), nullable=False)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("application_evidence.id", ondelete="CASCADE"), nullable=False, index=True
    )
    escalation_type: Mapped[str] = mapped_column(String(80), nullable=False, default="evidence_expired")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open", index=True)
    severity: Mapped[str] = mapped_column(String(30), nullable=False, default="high")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
