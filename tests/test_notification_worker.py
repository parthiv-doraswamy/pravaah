"""Tests for scheduled expiry monitoring and overdue compliance escalation."""

from datetime import date, timedelta

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.escalation import ComplianceEscalation
from app.models.notification import NotificationRecord
from app.models.workflow import ApplicationEvent
from app.services.notification_jobs import run_expiry_monitoring


def test_worker_queues_expiry_alerts_and_escalates_long_expired_evidence(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    today = date(2026, 10, 22)
    with session_factory() as db:
        institution = Institution(name="Worker Test College", code="WK-001", region_code="REGION-W")
        db.add(institution)
        db.flush()
        owner = User(
            email="worker-owner@example.test", full_name="Worker Owner", role="institution_user",
            institution_id=institution.id,
        )
        second_owner = User(
            email="worker-owner-2@example.test", full_name="Worker Owner Two", role="institution_user",
            institution_id=institution.id,
        )
        case = Application(
            application_number="PVH-WK-001", title="Worker test case", status="under_scrutiny",
            institution_id=institution.id,
        )
        db.add_all([owner, second_owner, case])
        db.flush()
        db.add_all([
            ApplicationEvidence(
                application_id=case.id, title="Expired certificate", category="accreditation",
                expires_on=today - timedelta(days=9),
            ),
            ApplicationEvidence(
                application_id=case.id, title="Upcoming certificate", category="fire_safety",
                expires_on=today + timedelta(days=4),
            ),
        ])
        db.commit()

    with session_factory() as db:
        result = run_expiry_monitoring(db, today=today)
    assert result["notifications_queued"] == 6
    assert result["evidence_records_checked"] == 2
    assert result["escalations_opened"] == 1

    with session_factory() as db:
        assert db.query(ComplianceEscalation).filter_by(status="open").count() == 1
        assert db.query(NotificationRecord).filter_by(notification_type="compliance_escalation").count() == 2
        assert db.query(ApplicationEvent).filter_by(event_type="compliance_escalation_opened").count() == 1
        assert db.query(ApplicationEvent).filter_by(event_type="expiry_notification_queued").count() == 2


def test_worker_is_idempotent_across_repeated_scans(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    today = date(2026, 10, 22)
    with session_factory() as db:
        institution = Institution(name="Idempotent Worker College", code="WK-002", region_code="REGION-W")
        db.add(institution)
        db.flush()
        owner = User(
            email="worker-idempotent@example.test", full_name="Worker Owner",
            role="institution_user", institution_id=institution.id,
        )
        case = Application(
            application_number="PVH-WK-002", title="Idempotency case", status="under_scrutiny",
            institution_id=institution.id,
        )
        db.add_all([owner, case])
        db.flush()
        db.add(ApplicationEvidence(
            application_id=case.id, title="Expired certificate", category="other",
            expires_on=today - timedelta(days=12),
        ))
        db.commit()

    with session_factory() as db:
        first = run_expiry_monitoring(db, today=today)
    with session_factory() as db:
        second = run_expiry_monitoring(db, today=today)

    assert first["notifications_queued"] == 2
    assert first["evidence_records_checked"] == 1
    assert first["escalations_opened"] == 1
    assert second["notifications_queued"] == 0
    assert second["escalations_opened"] == 0
    with session_factory() as db:
        assert db.query(ComplianceEscalation).count() == 1
        assert db.query(NotificationRecord).count() == 2


def test_escalation_can_be_listed_and_resolved_by_reviewer(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    today = date(2026, 10, 22)
    with session_factory() as db:
        institution = Institution(name="Escalation Review College", code="WK-004", region_code="REGION-W")
        db.add(institution)
        db.flush()
        owner = User(
            email="escalation-owner@example.test", full_name="Institution Owner",
            role="institution_user", institution_id=institution.id,
        )
        reviewer = User(
            email="escalation-reviewer@example.test", full_name="Review Officer",
            role="scrutiny_officer", password_hash=hash_password("Test-password-123!"),
        )
        case = Application(
            application_number="PVH-WK-004", title="Escalation review case",
            status="under_scrutiny", institution_id=institution.id,
        )
        db.add_all([owner, reviewer, case])
        db.flush()
        db.add(ApplicationEvidence(
            application_id=case.id, title="Overdue certificate", category="other",
            expires_on=today - timedelta(days=10),
        ))
        db.commit()

    with session_factory() as db:
        run_expiry_monitoring(db, today=today)
    login = client.post("/api/v1/auth/login", json={
        "email": "escalation-reviewer@example.test", "password": "Test-password-123!",
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    listed = client.get("/api/v1/compliance/escalations", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    escalation_id = listed.json()[0]["id"]
    resolved = client.post(f"/api/v1/compliance/escalations/{escalation_id}/resolve", headers=headers)
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["resolved_at"] is not None
