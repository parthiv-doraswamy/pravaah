"""Policy-configured deadline reminder and escalation tests."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.api.v1.routes.workflow import activate_policy_version, create_policy_version
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.notification import NotificationRecord
from app.models.workflow import ApplicationEvent
from app.schemas.workflow import PolicyCreate
from app.services.notification_jobs import run_expiry_monitoring, run_policy_deadline_monitoring
from app.services.workflow import append_event


def _setup(db, suffix: str):
    institution = Institution(
        name=f"Deadline Institution {suffix}",
        code=f"DL-{suffix}",
        region_code=f"REGION-{suffix}",
    )
    db.add(institution)
    db.flush()
    users = {}
    for role in (
        "institution_user", "scrutiny_officer", "bureau_officer",
        "competent_authority", "policy_admin", "evc_coordinator",
    ):
        user = User(
            email=f"deadline-{suffix}-{role}@example.test",
            full_name=f"Deadline {role}",
            role=role,
            institution_id=institution.id if role == "institution_user" else None,
        )
        db.add(user)
        users[role] = user
    application = Application(
        application_number=f"PVH-DL-{suffix}",
        title="Deadline test application",
        status="submitted",
        summary="Synthetic deadline test",
        institution_id=institution.id,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    for user in users.values():
        db.refresh(user)
    return users, application


def _create_policy(db, admin, suffix: str, deadlines: list[dict]):
    payload = PolicyCreate(
        policy_key="application_workflow",
        version=1,
        title=f"Synthetic deadline policy {suffix}",
        description="Synthetic test policy; not official AICTE guidance.",
        effective_from=datetime.now(UTC) - timedelta(days=1),
        source_label="Synthetic test policy",
        rules={"deadlines": deadlines},
    )
    create_policy_version(payload, db, admin)
    activate_policy_version("application_workflow", 1, db, admin)


def test_policy_deadlines_queue_reminders_then_idempotent_escalation(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        users, application = _setup(db, "001")
        _create_policy(db, users["policy_admin"], "001", [
            {
                "event": "submitted",
                "deadline_days": 3,
                "reminder_days_before": [3],
                "escalation_days_after": 2,
            }
        ])
        append_event(
            db, application_id=application.id, event_type="status_transition",
            from_status="draft", to_status="submitted", actor_user_id=users["institution_user"].id,
        )
        db.commit()
        event = db.scalar(select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type == "status_transition",
        ))
        run_at = event.occurred_at.replace(tzinfo=UTC) + timedelta(minutes=1)
        first = run_policy_deadline_monitoring(db, now=run_at)
        assert first["notifications_queued"] == 2
        assert first["escalations_notified"] == 0

        overdue = run_at + timedelta(days=6)
        second = run_policy_deadline_monitoring(db, now=overdue)
        assert second["escalations_notified"] == 2
        third = run_policy_deadline_monitoring(db, now=overdue + timedelta(days=1))
        assert third["escalations_notified"] == 0

        records = list(db.scalars(select(NotificationRecord).where(
            NotificationRecord.application_id == application.id
        )).all())
        assert sum(item.notification_type == "workflow_deadline_reminder" for item in records) == 2
        assert sum(item.notification_type == "workflow_deadline_escalation" for item in records) == 2
        audit = list(db.scalars(select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type == "workflow_deadline_escalation_notified",
        )).all())
        assert len(audit) == 1


def test_evidence_expiry_policy_controls_reminder_windows_and_escalation(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    today = date(2026, 10, 23)
    with session_factory() as db:
        users, application = _setup(db, "002")
        _create_policy(db, users["policy_admin"], "002", [
            {
                "event": "evidence_expiry",
                "deadline_days": 7,
                "reminder_days_before": [7, 1],
                "escalation_days_after": 3,
            }
        ])
        db.add(ApplicationEvidence(
            application_id=application.id,
            title="Expired synthetic certificate",
            category="other",
            expires_on=today - timedelta(days=4),
        ))
        db.add(ApplicationEvidence(
            application_id=application.id,
            title="Not-yet-due synthetic certificate",
            category="other",
            expires_on=today + timedelta(days=5),
        ))
        db.commit()
        result = run_expiry_monitoring(db, today=today)
        assert result["escalations_opened"] == 1
        records = list(db.scalars(select(NotificationRecord).where(
            NotificationRecord.application_id == application.id
        )).all())
        assert sum(item.notification_type == "evidence_expiry" for item in records) == 1
        assert sum(item.notification_type == "compliance_escalation" for item in records) == 1
        assert not any(
            item.title.startswith("Evidence expires in 5 days") for item in records
        )
