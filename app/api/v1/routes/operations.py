"""Role-scoped operational metrics for the workspace dashboard."""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.core.clock import utc_today
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evc_visit import EVCVisit
from app.models.evidence import ApplicationEvidence
from app.models.escalation import ComplianceEscalation
from app.models.notification import NotificationRecord
from app.models.undertaking import ComplianceSubmission
from app.schemas.operations import OperationsMetrics

router = APIRouter()


@router.get("/metrics", response_model=OperationsMetrics, summary="Get scoped operations dashboard metrics")
def operations_metrics(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OperationsMetrics:
    """Aggregate current operational load only across applications visible to this user."""
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    visible_app_ids = select(visible_ids.c.id)
    today = utc_today()

    status_rows = db.execute(
        select(Application.status, func.count(Application.id))
        .where(Application.id.in_(visible_app_ids))
        .group_by(Application.status)
    ).all()
    by_status = {status: count for status, count in status_rows}
    total = sum(by_status.values())
    completed = by_status.get("completed", 0)
    active = sum(count for status, count in by_status.items() if status not in {"completed", "withdrawn"})
    awaiting = sum(
        count for status, count in by_status.items()
        if status in {
            "submitted", "scrutiny", "under_scrutiny", "re_scrutiny",
            "awaiting_institution_response", "clarification_requested",
            "committee_review", "pending_authority_decision", "decision_pending",
        }
    )

    pending_submissions = db.scalar(
        select(func.count(ComplianceSubmission.id)).where(
            ComplianceSubmission.application_id.in_(visible_app_ids),
            ComplianceSubmission.status == "submitted",
        )
    ) or 0
    expired_evidence = db.scalar(
        select(func.count(ApplicationEvidence.id))
        .where(ApplicationEvidence.application_id.in_(visible_app_ids), ApplicationEvidence.expires_on < today)
    ) or 0
    due_evidence = db.scalar(
        select(func.count(ApplicationEvidence.id)).where(
            ApplicationEvidence.application_id.in_(visible_app_ids),
            ApplicationEvidence.expires_on >= today,
            ApplicationEvidence.expires_on <= today + timedelta(days=7),
        )
    ) or 0
    open_escalations = db.scalar(
        select(func.count(ComplianceEscalation.id)).where(
            ComplianceEscalation.application_id.in_(visible_app_ids),
            ComplianceEscalation.status == "open",
        )
    ) or 0
    failed_notifications = db.scalar(
        select(func.count(NotificationRecord.id)).where(
            NotificationRecord.application_id.in_(visible_app_ids),
            NotificationRecord.delivery_status == "failed",
        )
    ) or 0
    pending_reports = db.scalar(
        select(func.count(EVCVisit.id)).where(
            EVCVisit.application_id.in_(visible_app_ids),
            EVCVisit.status == "completed",
            EVCVisit.report_status != "submitted",
        )
    ) or 0

    return OperationsMetrics(
        as_of=today,
        total_applications=total,
        active_applications=active,
        awaiting_review=awaiting,
        completed_applications=completed,
        applications_by_status=by_status,
        submissions_pending_review=pending_submissions,
        expired_evidence=expired_evidence,
        evidence_due_within_7_days=due_evidence,
        open_escalations=open_escalations,
        failed_notifications=failed_notifications,
        evc_reports_pending=pending_reports,
    )
