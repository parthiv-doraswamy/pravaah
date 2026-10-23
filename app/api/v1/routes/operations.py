"""Role-scoped operational metrics for the workspace dashboard."""

from datetime import timedelta
from datetime import date

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
from app.schemas.operations import TaskInbox, TaskInboxItem
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
    active = sum(count for status, count in by_status.items() if status not in {"completed", "withdrawn", "approved", "rejected"})
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


_TASK_ROLE_STATUSES: dict[str, dict[str, tuple[str, str, str, str]]] = {
    "institution_user": {
        "clarification_requested": ("Respond to clarification", "Update the application and resubmit", "high", "detail"),
        "returned": ("Revise and resubmit application", "Address the return notes before resubmission", "high", "detail"),
        "draft": ("Complete draft application", "Finish the draft and submit it for scrutiny", "low", "detail"),
    },
    "scrutiny_officer": {
        "submitted": ("Start application scrutiny", "Review the submitted application", "high", "detail"),
        "under_scrutiny": ("Continue application scrutiny", "Record the next scrutiny action", "medium", "detail"),
        "scrutiny": ("Continue application scrutiny", "Record the next scrutiny action", "medium", "detail"),
        "re_scrutiny": ("Complete re-scrutiny", "Review the institution's updated submission", "high", "detail"),
    },
    "regional_officer": {
        "submitted": ("Review submitted application", "Check the application for regional review", "high", "detail"),
        "under_scrutiny": ("Continue regional review", "Review the current application status", "medium", "detail"),
        "re_scrutiny": ("Review corrected application", "Check the latest application version", "high", "detail"),
        "committee_review": ("Review committee case", "Follow up on the committee review", "medium", "detail"),
    },
    "bureau_officer": {
        "recommended_for_approval": ("Forward recommendation", "Move the recommendation to the next decision stage", "high", "detail"),
        "pending_authority_decision": ("Follow up on authority decision", "Check the pending decision stage", "medium", "detail"),
    },
    "competent_authority": {
        "pending_authority_decision": ("Record authority decision", "Review the case and record a decision", "high", "detail"),
        "decision_pending": ("Record authority decision", "Review the case and record a decision", "high", "detail"),
    },
    "policy_admin": {
        "submitted": ("Review submitted application", "Review the application workflow", "medium", "detail"),
        "pending_authority_decision": ("Monitor pending decision", "Check the authority decision queue", "medium", "detail"),
        "decision_pending": ("Monitor pending decision", "Check the authority decision queue", "medium", "detail"),
    },
    "system_admin": {
        "submitted": ("Monitor submitted application", "Check the application workflow", "low", "detail"),
        "pending_authority_decision": ("Monitor pending decision", "Check the authority decision queue", "low", "detail"),
        "decision_pending": ("Monitor pending decision", "Check the authority decision queue", "low", "detail"),
    },
}


@router.get("/inbox", response_model=TaskInbox, summary="Get the current user's unified task inbox")
def task_inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TaskInbox:
    """Collect actionable workflow items while enforcing server-side visibility and role rules."""
    today = utc_today()
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).order_by(None).subquery()
    visible_app_ids = select(visible_ids.c.id)
    tasks: list[TaskInboxItem] = []

    def add_task(
        task_id: str, task_type: str, title: str, description: str, priority: str,
        status: str, application: Application, created_at: date, action_view: str,
        due_date: date | None = None,
    ) -> None:
        tasks.append(TaskInboxItem(
            task_id=task_id, task_type=task_type, title=title, description=description,
            priority=priority, status=status, application_id=str(application.id),
            application_number=application.application_number, application_title=application.title,
            institution_name=application.institution.name, created_at=created_at,
            due_date=due_date, action_view=action_view,
        ))

    # Application workflow tasks are tailored to the authenticated role.
    rules = _TASK_ROLE_STATUSES.get(user.role, {})
    if rules:
        applications = db.scalars(scoped_applications_statement(user).order_by(Application.updated_at.asc())).all()
        for application in applications:
            rule = rules.get(application.status)
            if rule:
                title, description, priority, action_view = rule
                add_task(
                    f"application:{application.id}", "application_workflow", title, description,
                    priority, application.status, application,
                    (application.submitted_at or application.updated_at or application.created_at).date(),
                    action_view,
                )

    if user.role in {"scrutiny_officer", "regional_officer", "bureau_officer", "competent_authority", "policy_admin", "system_admin"}:
        rows = db.execute(
            select(ComplianceSubmission, Application)
            .join(Application, Application.id == ComplianceSubmission.application_id)
            .where(Application.id.in_(visible_app_ids), ComplianceSubmission.status == "submitted")
            .order_by(ComplianceSubmission.submitted_at.asc().nullsfirst())
        ).all()
        for submission, application in rows:
            submitted = submission.submitted_at or submission.created_at
            add_task(
                f"submission:{submission.id}", "submission_review", "Review compliance submission",
                f"{submission.title} · version {submission.version}", "high", submission.status,
                application, submitted.date(), "detail",
            )

    if user.role == "institution_user":
        rows = db.execute(
            select(ComplianceSubmission, Application)
            .join(Application, Application.id == ComplianceSubmission.application_id)
            .where(Application.id.in_(visible_app_ids), ComplianceSubmission.status == "changes_requested")
            .order_by(ComplianceSubmission.updated_at.asc())
        ).all()
        for submission, application in rows:
            add_task(
                f"correction:{submission.id}", "submission_correction", "Correct compliance submission",
                submission.review_notes or f"Update {submission.title} and submit a new version",
                "high", submission.status, application, submission.updated_at.date(), "detail",
            )

    evidence_rows = db.execute(
        select(ApplicationEvidence, Application)
        .join(Application, Application.id == ApplicationEvidence.application_id)
        .where(
            Application.id.in_(visible_app_ids), ApplicationEvidence.lifecycle_status == "current",
            ApplicationEvidence.expires_on.is_not(None),
            ApplicationEvidence.expires_on <= today + timedelta(days=30),
        )
        .order_by(ApplicationEvidence.expires_on.asc())
    ).all()
    for evidence, application in evidence_rows:
        expiry = evidence.expires_on
        if expiry is None:
            continue
        remaining = (expiry - today).days
        priority = "high" if remaining < 0 else "medium" if remaining <= 7 else "low"
        label = "expired" if remaining < 0 else "expires today" if remaining == 0 else f"expires in {remaining} day(s)"
        add_task(
            f"evidence:{evidence.id}", "evidence_expiry", "Review evidence validity",
            f"{evidence.title} {label}", priority, label, application,
            evidence.updated_at.date(), "compliance", expiry,
        )

    escalation_rows = db.execute(
        select(ComplianceEscalation, Application)
        .join(Application, Application.id == ComplianceEscalation.application_id)
        .where(Application.id.in_(visible_app_ids), ComplianceEscalation.status == "open")
        .order_by(ComplianceEscalation.triggered_at.asc())
    ).all()
    for escalation, application in escalation_rows:
        add_task(
            f"escalation:{escalation.id}", "compliance_escalation", "Resolve compliance escalation",
            escalation.summary, "high", escalation.status, application,
            escalation.triggered_at.date(), "compliance",
        )

    if user.role in {"evc_coordinator", "bureau_officer", "policy_admin", "system_admin"}:
        visit_rows = db.execute(
            select(EVCVisit, Application)
            .join(Application, Application.id == EVCVisit.application_id)
            .where(
                Application.id.in_(visible_app_ids), EVCVisit.status == "completed",
                EVCVisit.report_status != "submitted",
            )
            .order_by(EVCVisit.scheduled_for.asc())
        ).all()
        for visit, application in visit_rows:
            add_task(
                f"evc-report:{visit.id}", "evc_report", "Complete EVC outcome report",
                f"Visit completed on {visit.scheduled_for.date().isoformat()}; report is {visit.report_status}",
                "high", visit.report_status, application, visit.updated_at.date(), "evc",
            )

    notification_rows = db.execute(
        select(NotificationRecord, Application)
        .join(Application, Application.id == NotificationRecord.application_id)
        .where(
            Application.id.in_(visible_app_ids), NotificationRecord.recipient_user_id == user.id,
            NotificationRecord.delivery_status == "failed",
        )
        .order_by(NotificationRecord.created_at.asc())
    ).all()
    for notification, application in notification_rows:
        add_task(
            f"notification:{notification.id}", "notification_delivery", "Recover failed notification",
            notification.last_error or notification.message, "medium", notification.delivery_status,
            application, notification.created_at.date(), "notifications",
        )

    priority_order = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(key=lambda item: (priority_order[item.priority], item.created_at, item.task_id))
    by_priority = {key: sum(item.priority == key for item in tasks) for key in ("high", "medium", "low")}
    by_type: dict[str, int] = {}
    for item in tasks:
        by_type[item.task_type] = by_type.get(item.task_type, 0) + 1
    return TaskInbox(
        as_of=today, total=len(tasks), by_priority=by_priority, by_type=by_type, items=tasks[:100],
    )
