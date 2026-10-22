"""API representation for compliance escalation records."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EscalationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    evidence_id: UUID
    escalation_type: str
    status: str
    severity: str
    summary: str
    triggered_at: datetime
    resolved_at: datetime | None
