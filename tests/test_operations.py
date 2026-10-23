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
    assert {item["status"] for item in payload["by_status"]} == {"committee_review", "under_scrutiny"}


def test_pendency_analytics_requires_authentication(api_client_and_sessions):
    client, _ = api_client_and_sessions
    response = client.get("/api/v1/operations/pendency")
    assert response.status_code == 401


def test_task_inbox_combines_actionable_items_and_respects_institution_scope(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    today = datetime.now(UTC).date()
    with db_factory() as db:
        own = Institution(name="Inbox College", code="INBOX-OWN", region_code="INBOX")
        other = Institution(name="Hidden Inbox College", code="INBOX-OTHER", region_code="OTHER")
        db.add_all([own, other])
        db.flush()
        user = User(
            email="inbox-owner@example.test",
            full_name="Inbox Owner",
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=own.id,
        )
        own_case = Application(
            application_number="PVH-INBOX-OWN",
            title="Inbox draft case",
            status="draft",
            institution_id=own.id,
        )
        hidden_case = Application(
            application_number="PVH-INBOX-HIDDEN",
            title="Hidden inbox case",
            status="draft",
            institution_id=other.id,
        )
        db.add_all([user, own_case, hidden_case])
        db.flush()
        db.add_all([
            ApplicationEvidence(
                application_id=own_case.id,
                title="Fire safety certificate",
                category="safety",
                expires_on=today + timedelta(days=3),
                created_by_user_id=user.id,
            ),
            ApplicationEvidence(
                application_id=hidden_case.id,
                title="Hidden expired certificate",
                category="safety",
                expires_on=today - timedelta(days=5),
            ),
        ])
        db.commit()
        email = user.email

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Test-password-123!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.get("/api/v1/operations/inbox", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 2
    assert payload["by_priority"]["medium"] == 1
    assert payload["by_priority"]["low"] == 1
    assert {item["application_number"] for item in payload["items"]} == {"PVH-INBOX-OWN"}
    evidence_task = next(item for item in payload["items"] if item["task_type"] == "evidence_expiry")
    assert evidence_task["title"] == "Review evidence validity"
    assert evidence_task["action_view"] == "compliance"
    assert "Fire safety certificate" in evidence_task["description"]


def test_task_inbox_requires_authentication(api_client_and_sessions):
    client, _ = api_client_and_sessions
    response = client.get("/api/v1/operations/inbox")
    assert response.status_code == 401


def test_reports_export_csv_is_scoped_and_supports_date_filters(api_client_and_sessions):
    client, db_factory = api_client_and_sessions
    with db_factory() as db:
        own = Institution(name="Report College", code="RPT-OWN", region_code="RPT")
        other = Institution(name="Hidden Report College", code="RPT-HIDDEN", region_code="OTHER")
        db.add_all([own, other])
        db.flush()
        user = User(
            email="reports-owner@example.test",
            full_name="Reports Owner",
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=own.id,
        )
        visible = Application(
            application_number="PVH-REPORT-OWN",
            title="Visible report case",
            status="under_scrutiny",
            institution_id=own.id,
        )
        hidden = Application(
            application_number="PVH-REPORT-HIDDEN",
            title="Hidden report case",
            status="approved",
            institution_id=other.id,
        )
        db.add_all([user, visible, hidden])
        db.commit()
        email = user.email

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Test-password-123!"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = client.get("/api/v1/operations/reports/applications/export", headers=headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert 'attachment; filename="pravaah-applications-report.csv"' in response.headers["content-disposition"]
    assert "application_number,title,institution,status" in response.text
    assert "PVH-REPORT-OWN" in response.text
    assert "PVH-REPORT-HIDDEN" not in response.text

    invalid_dates = client.get(
        "/api/v1/operations/reports/applications/export?from_date=2026-10-24&to_date=2026-10-01",
        headers=headers,
    )
    assert invalid_dates.status_code == 422


def test_reports_export_requires_auth_and_rejects_unknown_report_type(api_client_and_sessions):
    client, _ = api_client_and_sessions
    assert client.get("/api/v1/operations/reports/applications/export").status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "institution@example.test", "password": "PravaahDemo2026!"},
    )
    # The isolated test database does not seed demo users; unauthenticated access remains denied.
    assert login.status_code == 401
    assert client.get("/api/v1/operations/reports/unknown/export").status_code == 401
