"""Contracts for computed compliance and expiry summaries."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class EvidenceAlert(BaseModel):
    evidence_id: UUID
    application_id: UUID
    application_number: str
    application_title: str
    title: str
    category: str
    policy_key: str | None
    expires_on: date
    days_remaining: int
    severity: str


class ComplianceOverview(BaseModel):
    as_of: date
    total_evidence: int
    expired: int
    due_within_1_day: int
    due_within_7_days: int
    due_within_30_days: int
    without_expiry: int
    alerts: list[EvidenceAlert]
    warning_windows_days: list[int]
    warning_source: str
