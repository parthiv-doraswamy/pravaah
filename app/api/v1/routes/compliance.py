"""Read-only compliance overview derived from recorded evidence expiry dates."""

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user, require_roles
from app.auth.permissions import COMPLIANCE_ESCALATION_RESOLVER_ROLES
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.escalation import ComplianceEscalation
from app.schemas.escalations import EscalationResponse
from app.services.workflow import append_event
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



@router.get("/escalations", response_model=list[EscalationResponse], summary="List compliance escalations in the current user's scope")
def list_escalations(
    open_only: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ComplianceEscalation]:
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    statement = select(ComplianceEscalation).where(
        ComplianceEscalation.application_id.in_(select(visible_ids.c.id))
    )
    if open_only:
        statement = statement.where(ComplianceEscalation.status == "open")
    return list(db.scalars(statement.order_by(ComplianceEscalation.triggered_at.desc()).limit(100)).all())


@router.post(
    "/escalations/{escalation_id}/resolve",
    response_model=EscalationResponse,
    summary="Resolve a compliance escalation",
)
def resolve_escalation(
    escalation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*COMPLIANCE_ESCALATION_RESOLVER_ROLES)),
) -> ComplianceEscalation:
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    escalation = db.scalar(
        select(ComplianceEscalation)
        .where(
            ComplianceEscalation.id == escalation_id,
            ComplianceEscalation.application_id.in_(select(visible_ids.c.id)),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if escalation is None:
        raise HTTPException(status_code=404, detail="Escalation not found")
    if escalation.status != "resolved":
        now = datetime.now(UTC)
        escalation.status = "resolved"
        escalation.resolved_at = now
        application = db.get(Application, escalation.application_id)
        append_event(
            db,
            application_id=escalation.application_id,
            event_type="compliance_escalation_resolved",
            from_status=application.status if application else None,
            to_status=application.status if application else None,
            actor_user_id=user.id,
            metadata={"escalation_id": str(escalation.id), "evidence_id": str(escalation.evidence_id)},
        )
        db.commit()
        db.refresh(escalation)
    return escalation
