"""Read-only compliance overview derived from recorded evidence expiry dates."""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.schemas.compliance import ComplianceOverview, EvidenceAlert

router = APIRouter()


@router.get("/overview", response_model=ComplianceOverview, summary="Summarize evidence expiry and compliance warnings")
def compliance_overview(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ComplianceOverview:
    """Return a scoped expiry overview; warning windows are synthetic demo defaults."""
    today = date.today()
    visible_applications = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    rows = db.execute(
        select(ApplicationEvidence, Application.application_number, Application.title)
        .join(Application, Application.id == ApplicationEvidence.application_id)
        .where(Application.id.in_(select(visible_applications.c.id)))
        .order_by(ApplicationEvidence.expires_on.asc().nullslast(), ApplicationEvidence.title)
    ).all()

    expired = due_1 = due_7 = due_30 = no_expiry = 0
    alerts: list[EvidenceAlert] = []
    for evidence, application_number, application_title in rows:
        if evidence.expires_on is None:
            no_expiry += 1
            continue
        days = (evidence.expires_on - today).days
        if days < 0:
            expired += 1
            severity = "expired"
        elif days <= 1:
            due_1 += 1
            severity = "urgent"
        elif days <= 7:
            due_7 += 1
            severity = "warning"
        elif days <= 30:
            due_30 += 1
            severity = "upcoming"
        else:
            continue
        alerts.append(EvidenceAlert(
            evidence_id=evidence.id,
            application_id=evidence.application_id,
            application_number=application_number,
            application_title=application_title,
            title=evidence.title,
            category=evidence.category,
            policy_key=evidence.policy_key,
            expires_on=evidence.expires_on,
            days_remaining=days,
            severity=severity,
        ))

    return ComplianceOverview(
        as_of=today,
        total_evidence=len(rows),
        expired=expired,
        due_within_1_day=due_1,
        due_within_7_days=due_7,
        due_within_30_days=due_30,
        without_expiry=no_expiry,
        alerts=alerts,
        warning_windows_days=[30, 7, 1],
        warning_source="Synthetic PRAVAAH demo defaults; not official AICTE deadlines",
    )
