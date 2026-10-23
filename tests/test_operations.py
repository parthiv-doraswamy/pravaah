"""Integration tests for role-scoped operations dashboard metrics."""

from datetime import UTC, date, datetime, timedelta

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.evc_visit import EVCVisit
from app.models.evidence import ApplicationEvidence
from app.models.escalation import ComplianceEscalation
from app.models.notification import NotificationRecord
from app.models.undertaking import ComplianceSubmission


def test_operations_metrics_are_aggregated_and_institution_scoped(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    with db_factory() as db:
        own_institution = Institution(name="Own College", code="OPS-OWN", region_code="OPS")
        other_institution = Institution(name="Other College", code="OPS-OTHER", region_code="OTHER")
        db.add_all([own_institution, other_institution])
        db.flush()
        owner = User(
            email="ops-owner@example.test",
            full_name="Operations Owner",
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=own_institution.id,
        )
        own_case = Application(
            application_number="PVH-OPS-OWN",
            title="Scoped scrutiny case",
            status="under_scrutiny",
            institution_id=own_institution.id,
        )
        other_case = Application(
            application_number="PVH-OPS-OTHER",
            title="Out of scope case",
            status="approved",
            institution_id=other_institution.id,
        )
        db.add_all([owner, own_case, other_case])
        db.flush()

        expired = ApplicationEvidence(
            application_id=own_case.id,
            title="Expired certificate",
            category="accreditation",
            expires_on=date.today() - timedelta(days=2),
            created_by_user_id=owner.id,
        )
        due = ApplicationEvidence(
            application_id=own_case.id,
            title="Due certificate",
            category="accreditation",
            expires_on=date.today() + timedelta(days=4),
            created_by_user_id=owner.id,
        )
        db.add_all([
            expired,
            due,
            ApplicationEvidence(
                application_id=other_case.id,
                title="Other institution certificate",
                category="accreditation",
                expires_on=date.today() - timedelta(days=1),
            ),
        ])
        db.flush()
        db.add_all([
            ComplianceSubmission(
                application_id=own_case.id,
                submission_type="annual_undertaking",
                title="Annual undertaking",
                declaration="I confirm the compliance details are accurate.",
                evidence_ids=[str(due.id)],
                status="submitted",
                version=1,
            ),
            NotificationRecord(
                recipient_user_id=owner.id,
                application_id=own_case.id,
                evidence_id=expired.id,
                dedupe_key="ops-failed-notification",
                notification_type="evidence_expiry",
                title="Delivery failed",
                message="Please review the evidence.",
                severity="warning",
                delivery_status="failed",
            ),
            ComplianceEscalation(
                dedupe_key="ops-open-escalation",
                application_id=own_case.id,
                evidence_id=expired.id,
                summary="Evidence is overdue",
                status="open",
                severity="high",
            ),
            EVCVisit(
                application_id=own_case.id,
                scheduled_for=datetime.now(UTC) - timedelta(days=1),
                mode="virtual",
                status="completed",
                report_status="draft",
            ),
        ])
        db.commit()
        email = owner.email

    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test-password-123!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/operations/metrics", headers=headers)
    assert response.status_code == 200
    metrics = response.json()
    assert metrics["total_applications"] == 1
    assert metrics["active_applications"] == 1
    assert metrics["awaiting_review"] == 1
    assert metrics["completed_applications"] == 0
    assert metrics["applications_by_status"] == {"under_scrutiny": 1}
    assert metrics["submissions_pending_review"] == 1
    assert metrics["expired_evidence"] == 1
    assert metrics["evidence_due_within_7_days"] == 1
    assert metrics["open_escalations"] == 1
    assert metrics["failed_notifications"] == 1
    assert metrics["evc_reports_pending"] == 1
    assert metrics["as_of"]


def test_operations_metrics_requires_authentication(api_client_and_sessions):
    client, _ = api_client_and_sessions
    response = client.get("/api/v1/operations/metrics")
    assert response.status_code == 401


def test_pendency_analytics_reports_aging_and_respects_institution_scope(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    with db_factory() as db:
        own = Institution(name="Pendency College", code="PEND-OWN", region_code="PEND")
        other = Institution(name="Out of Scope College", code="PEND-OTHER", region_code="OTHER")
        db.add_all([own, other])
        db.flush()
        user = User(
            email="pendency-owner@example.test",
            full_name="Pendency Owner",
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=own.id,
        )
        old_case = Application(
            application_number="PVH-PEND-OLD",
            title="Old pending case",
            status="under_scrutiny",
            institution_id=own.id,
            submitted_at=datetime.now(UTC) - timedelta(days=20),
        )
        recent_case = Application(
            application_number="PVH-PEND-RECENT",
            title="Recent pending case",
            status="committee_review",
            institution_id=own.id,
            submitted_at=datetime.now(UTC) - timedelta(days=5),
        )
        hidden_case = Application(
            application_number="PVH-PEND-HIDDEN",
            title="Hidden old case",
            status="submitted",
            institution_id=other.id,
            submitted_at=datetime.now(UTC) - timedelta(days=30),
        )
        db.add_all([user, old_case, recent_case, hidden_case])
        db.commit()
        email = user.email

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Test-password-123!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/operations/pendency", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_pending"] == 2
    assert payload["aging_buckets"]["15+_days"] == 1
    assert payload["aging_buckets"]["3-7_days"] == 1
    assert [item["application_number"] for item in payload["oldest_items"]] == [
        "PVH-PEND-OLD",
        "PVH-PEND-RECENT",
    ]
    assert payload["by_status"][0]["status"] == "committee_review" or payload["by_status"][0]["status"] == "under_scrutiny"
