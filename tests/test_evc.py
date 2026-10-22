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
