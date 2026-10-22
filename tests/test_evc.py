"""Integration tests for scoped EVC visit scheduling."""

from datetime import UTC, datetime, timedelta

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.workflow import ApplicationEvent


def _scheduler(session_factory, *, email: str, role: str = "evc_coordinator"):
    with session_factory() as db:
        institution = Institution(
            name=f"EVC Institution {email}", code=f"EVC-{email.split('@')[0].upper()}",
            region_code="EVC-REGION",
        )
        db.add(institution)
        db.flush()
        user = User(
            email=email, full_name="EVC Scheduler", role=role,
            password_hash=hash_password("Test-password-123!"), institution_id=institution.id,
        )
        application = Application(
            application_number=f"PVH-{email.split('@')[0].upper()}",
            title="EVC test application", status="under_scrutiny", institution_id=institution.id,
        )
        db.add_all([user, application])
        db.commit()
        return institution.id, application.id


def _login(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test-password-123!"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_evc_coordinator_can_schedule_and_complete_visit(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    _, application_id = _scheduler(session_factory, email="evc-coord@example.test")
    token = _login(client, "evc-coord@example.test")
    headers = {"Authorization": f"Bearer {token}"}
    scheduled_for = (datetime.now(UTC) + timedelta(days=5)).isoformat()

    created = client.post(
        "/api/v1/evc/visits",
        headers=headers,
        json={
            "application_id": str(application_id), "scheduled_for": scheduled_for,
            "mode": "onsite", "location": "Demo campus, Hyderabad",
        },
    )
    assert created.status_code == 201, created.text
    visit = created.json()
    assert visit["status"] == "scheduled"
    assert visit["mode"] == "onsite"

    listed = client.get("/api/v1/evc/visits", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [visit["id"]]

    completed = client.post(
        f"/api/v1/evc/visits/{visit['id']}/status",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    with session_factory() as db:
        events = db.query(ApplicationEvent).filter_by(application_id=application_id).all()
        assert [event.event_type for event in events] == [
            "evc_visit_scheduled", "evc_visit_status_changed",
        ]


def test_institution_user_cannot_schedule_evc_visit(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    _, application_id = _scheduler(
        session_factory, email="institution-evc@example.test", role="institution_user",
    )
    token = _login(client, "institution-evc@example.test")
    response = client.post(
        "/api/v1/evc/visits",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "application_id": str(application_id),
            "scheduled_for": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "mode": "virtual",
        },
    )
    assert response.status_code == 403


def test_onsite_visit_requires_location(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    _, application_id = _scheduler(session_factory, email="evc-location@example.test")
    token = _login(client, "evc-location@example.test")
    response = client.post(
        "/api/v1/evc/visits",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "application_id": str(application_id),
            "scheduled_for": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "mode": "onsite",
        },
    )
    assert response.status_code == 422


def test_completed_visit_report_is_audited_and_immutable_after_submission(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    _, application_id = _scheduler(session_factory, email="evc-report@example.test")
    token = _login(client, "evc-report@example.test")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/evc/visits",
        headers=headers,
        json={
            "application_id": str(application_id),
            "scheduled_for": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "mode": "virtual",
        },
    )
    assert created.status_code == 201, created.text
    visit_id = created.json()["id"]
    completed = client.post(
        f"/api/v1/evc/visits/{visit_id}/status",
        headers=headers,
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text

    checklist = [
        {"key": key, "label": label, "result": "pass", "notes": None}
        for key, label in [
            ("governance", "Governance and approvals"),
            ("infrastructure", "Infrastructure readiness"),
            ("faculty", "Faculty availability"),
            ("curriculum", "Curriculum and programme"),
            ("safety", "Safety and accessibility"),
            ("records", "Records and evidence"),
        ]
    ]
    report = {
        "checklist": checklist,
        "outcome_summary": "Illustrative demo report; evidence reviewed during the visit.",
        "observations": "Synthetic demonstration notes only.",
        "submit": True,
    }
    submitted = client.put(f"/api/v1/evc/visits/{visit_id}/report", headers=headers, json=report)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["report_status"] == "submitted"
    assert submitted.json()["report_submitted_at"] is not None
    assert len(submitted.json()["checklist"]) == 6

    repeated = client.put(f"/api/v1/evc/visits/{visit_id}/report", headers=headers, json=report)
    assert repeated.status_code == 409

    with session_factory() as db:
        events = db.query(ApplicationEvent).filter_by(application_id=application_id).all()
        assert "evc_report_submitted" in [event.event_type for event in events]


def test_evc_report_cannot_be_submitted_with_unexplained_attention_item(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    _, application_id = _scheduler(session_factory, email="evc-report-validation@example.test")
    token = _login(client, "evc-report-validation@example.test")
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/evc/visits",
        headers=headers,
        json={
            "application_id": str(application_id),
            "scheduled_for": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
            "mode": "virtual",
        },
    )
    visit_id = created.json()["id"]
    client.post(f"/api/v1/evc/visits/{visit_id}/status", headers=headers, json={"status": "completed"})
    checklist = [
        {"key": key, "label": key.title(), "result": "pass", "notes": None}
        for key in ["governance", "infrastructure", "faculty", "curriculum", "safety", "records"]
    ]
    checklist[0]["result"] = "needs_attention"
    response = client.put(
        f"/api/v1/evc/visits/{visit_id}/report",
        headers=headers,
        json={
            "checklist": checklist,
            "outcome_summary": "Illustrative report with one unresolved checklist item.",
            "submit": True,
        },
    )
    assert response.status_code == 422
