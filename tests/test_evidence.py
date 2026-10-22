"""Integration tests for evidence registration, scope checks, and audit linkage."""

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.workflow import ApplicationEvent


def _login_and_case(client, session_factory, suffix: str):
    with session_factory() as db:
        institution = Institution(name=f"Evidence College {suffix}", code=f"EV-{suffix}", region_code="REGION-E")
        db.add(institution)
        db.flush()
        user = User(
            email=f"evidence-{suffix}@example.test",
            full_name="Evidence Test User",
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=institution.id,
        )
        application = Application(
            application_number=f"PVH-EV-{suffix}",
            title="Evidence registration case",
            status="draft",
            institution_id=institution.id,
        )
        db.add_all([user, application])
        db.commit()
        application_id = application.id
        institution_id = institution.id
    response = client.post(
        "/api/v1/auth/login",
        json={"email": f"evidence-{suffix}@example.test", "password": "Test-password-123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, application_id, institution_id


def test_evidence_registration_is_listed_and_added_to_audit_chain(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _login_and_case(client, session_factory, "001")
    response = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={
            "title": "Fire safety certificate",
            "category": "fire_safety",
            "reference_number": "FSC-2026-001",
            "issued_on": "2026-01-01",
            "expires_on": "2027-01-01",
            "policy_key": "EVIDENCE_EXPIRY",
            "notes": "Synthetic test evidence metadata",
        },
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Fire safety certificate"
    assert response.json()["expires_on"] == "2027-01-01"

    listing = client.get(f"/api/v1/applications/{application_id}/evidence", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1

    verification = client.get(f"/api/v1/applications/{application_id}/events/verify", headers=headers)
    assert verification.status_code == 200
    assert verification.json()["valid"] is True
    assert verification.json()["event_count"] == 1

    with session_factory() as db:
        event = db.query(ApplicationEvent).filter_by(application_id=application_id).one()
        assert event.event_type == "evidence_registered"
        assert event.event_metadata["title"] == "Fire safety certificate"


def test_evidence_expiry_cannot_precede_issue_date(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _login_and_case(client, session_factory, "002")
    response = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={"title": "Certificate", "category": "other", "issued_on": "2026-06-01", "expires_on": "2026-05-01"},
    )
    assert response.status_code == 422


def test_evidence_cannot_be_read_outside_institution_scope(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers_a, _, _ = _login_and_case(client, session_factory, "003")
    _, application_b, _ = _login_and_case(client, session_factory, "004")
    response = client.get(f"/api/v1/applications/{application_b}/evidence", headers=headers_a)
    assert response.status_code == 404
