"""Request and response schemas for EVC visit scheduling."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EVCEligibilityResponse(BaseModel):
    application_id: UUID
    eligible: bool
    reasons: list[str]
    active_visit_id: UUID | None
    eligible_application_statuses: list[str]


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


class EVCChecklistItem(BaseModel):
    key: Literal["governance", "infrastructure", "faculty", "curriculum", "safety", "records"]
    label: str = Field(min_length=2, max_length=160)
    result: Literal["pass", "needs_attention", "not_applicable"]
    notes: str | None = Field(default=None, max_length=1500)


class EVCReportUpdate(BaseModel):
    checklist: list[EVCChecklistItem] = Field(min_length=6, max_length=6)
    outcome_summary: str = Field(min_length=10, max_length=4000)
    observations: str | None = Field(default=None, max_length=10000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=100)
    submit: bool = False

    @model_validator(mode="after")
    def validate_checklist(self):
        keys = [item.key for item in self.checklist]
        expected = {"governance", "infrastructure", "faculty", "curriculum", "safety", "records"}
        if len(set(keys)) != len(keys) or set(keys) != expected:
            raise ValueError("Checklist must contain each of the six required demo sections exactly once")
        if self.submit and any(item.result == "needs_attention" and not (item.notes or "").strip() for item in self.checklist):
            raise ValueError("Add a note for each checklist item marked needs attention before submitting")
        return self


class EVCVisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    scheduled_for: datetime
    mode: str
    location: str | None
    notes: str | None
    status: str
    checklist: list[dict[str, object]] | None
    linked_evidence_ids: list[str] | None

    @field_validator("linked_evidence_ids", mode="before")
    @classmethod
    def normalize_legacy_evidence_ids(cls, value):
        """Keep old JSON values readable instead of failing the entire visit listing."""
        if value is None or not isinstance(value, list):
            return None
        return [str(item) for item in value if item is not None]

    outcome_summary: str | None
    observations: str | None
    report_status: str
    report_submitted_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

    @field_validator("checklist", mode="before")
    @classmethod
    def normalize_legacy_checklist(cls, value):
        """Convert pre-report EVC checklist maps to the current API list shape.

        Some existing demo visits store checklist as a JSON object such as
        {"campus_infrastructure": "pending"}. Normalize it at the API boundary
        so old rows remain readable without a destructive database migration.
        """
        if value is None or isinstance(value, list):
            return value
        if not isinstance(value, dict):
            return None

        result_map = {
            "pass": "pass",
            "passed": "pass",
            "complete": "pass",
            "completed": "pass",
            "verified": "pass",
            "needs_attention": "needs_attention",
            "fail": "needs_attention",
            "failed": "needs_attention",
            "issue": "needs_attention",
            "not_applicable": "not_applicable",
            "pending": "not_applicable",
            "not_started": "not_applicable",
        }
        normalized = []
        for key, result in value.items():
            raw_result = str(result).strip().lower()
            normalized.append({
                "key": str(key),
                "label": str(key).replace("_", " ").strip().title() or "Checklist item",
                "result": result_map.get(raw_result, "not_applicable"),
                "notes": None,
            })
        return normalized
