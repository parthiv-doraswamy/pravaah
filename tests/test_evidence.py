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


def test_compliance_overview_summarizes_expiry_windows(api_client_and_sessions):
    from datetime import date, timedelta

    from app.models.evidence import ApplicationEvidence

    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _login_and_case(client, session_factory, "005")
    today = date.today()
    with session_factory() as db:
        db.add_all([
            ApplicationEvidence(
                application_id=application_id, title="Expired certificate", category="fire_safety",
                expires_on=today - timedelta(days=2),
            ),
            ApplicationEvidence(
                application_id=application_id, title="Urgent certificate", category="accreditation",
                expires_on=today + timedelta(days=1),
            ),
            ApplicationEvidence(
                application_id=application_id, title="Upcoming certificate", category="other",
                expires_on=today + timedelta(days=20),
            ),
            ApplicationEvidence(
                application_id=application_id, title="Undated record", category="other",
            ),
        ])
        db.commit()

    response = client.get("/api/v1/compliance/overview", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_evidence"] == 4
    assert payload["expired"] == 1
    assert payload["due_within_1_day"] == 1
    assert payload["due_within_30_days"] == 1
    assert payload["without_expiry"] == 1
    assert payload["warning_windows_days"] == [30, 7, 1]
    assert "not official AICTE deadlines" in payload["warning_source"]


def test_compliance_overview_only_includes_visible_applications(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers_a, _, _ = _login_and_case(client, session_factory, "006")
    _, application_b, _ = _login_and_case(client, session_factory, "007")
    from app.models.evidence import ApplicationEvidence

    with session_factory() as db:
        db.add(ApplicationEvidence(
            application_id=application_b, title="Private evidence", category="other",
        ))
        db.commit()

    response = client.get("/api/v1/compliance/overview", headers=headers_a)
    assert response.status_code == 200
    assert response.json()["total_evidence"] == 0
    assert response.json()["alerts"] == []



def test_evidence_text_fields_are_trimmed_and_blank_values_rejected(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _login_and_case(client, session_factory, "008")
    response = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={
            "title": "   Fire safety certificate   ",
            "category": "   fire_safety   ",
            "reference_number": "   REF-008   ",
            "policy_key": "   EVIDENCE_EXPIRY   ",
        },
    )
    assert response.status_code == 201
    assert response.json()["title"] == "Fire safety certificate"
    assert response.json()["category"] == "fire_safety"
    assert response.json()["reference_number"] == "REF-008"
    assert response.json()["policy_key"] == "EVIDENCE_EXPIRY"

    invalid = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={"title": "   ", "category": "other"},
    )
    assert invalid.status_code == 422



def test_evidence_renewal_creates_linked_version_and_preserves_prior_record(api_client_and_sessions):
    from datetime import date, timedelta
    from uuid import UUID

    from app.models.evidence import ApplicationEvidence
    from app.models.workflow import ApplicationEvent

    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _login_and_case(client, session_factory, "009")
    created = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={
            "title": "Fire safety certificate",
            "category": "fire_safety",
            "reference_number": "FSC-OLD",
            "issued_on": str(date.today() - timedelta(days=300)),
            "expires_on": str(date.today() - timedelta(days=1)),
            "policy_key": "EVIDENCE_EXPIRY",
            "notes": "Original record remains historical evidence",
        },
    )
    assert created.status_code == 201, created.text
    prior_id = created.json()["id"]
    assert created.json()["version"] == 1
    assert created.json()["lifecycle_status"] == "current"

    renewed = client.post(
        f"/api/v1/applications/{application_id}/evidence/{prior_id}/renewals",
        headers=headers,
        json={
            "title": "Fire safety certificate",
            "category": "fire_safety",
            "reference_number": "FSC-NEW",
            "issued_on": str(date.today()),
            "expires_on": str(date.today() + timedelta(days=365)),
            "policy_key": "EVIDENCE_EXPIRY",
            "notes": "Renewed certificate",
        },
    )
    assert renewed.status_code == 201, renewed.text
    payload = renewed.json()
    assert payload["version"] == 2
    assert payload["supersedes_evidence_id"] == prior_id
    assert payload["lifecycle_status"] == "current"
    assert payload["reference_number"] == "FSC-NEW"

    listing = client.get(f"/api/v1/applications/{application_id}/evidence", headers=headers)
    assert listing.status_code == 200
    by_id = {item["id"]: item for item in listing.json()}
    assert by_id[prior_id]["lifecycle_status"] == "replaced"
    assert by_id[prior_id]["reference_number"] == "FSC-OLD"
    assert by_id[payload["id"]]["version"] == 2

    duplicate = client.post(
        f"/api/v1/applications/{application_id}/evidence/{prior_id}/renewals",
        headers=headers,
        json={
            "title": "Fire safety certificate",
            "category": "fire_safety",
            "issued_on": str(date.today()),
            "expires_on": str(date.today() + timedelta(days=500)),
        },
    )
    assert duplicate.status_code == 409

    with session_factory() as db:
        events = db.query(ApplicationEvent).filter_by(application_id=application_id).order_by(ApplicationEvent.sequence).all()
        assert [event.event_type for event in events] == ["evidence_registered", "evidence_renewed"]
        assert events[-1].event_metadata["prior_evidence_id"] == prior_id
        original = db.get(ApplicationEvidence, UUID(prior_id))
        assert original is not None
        assert original.reference_number == "FSC-OLD"
        assert original.version == 1


def test_evidence_renewal_requires_future_expiry_date(api_client_and_sessions):
    from datetime import date, timedelta

    client, session_factory = api_client_and_sessions
    headers, application_id, _ = _login_and_case(client, session_factory, "010")
    created = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={"title": "Certificate", "category": "other"},
    )
    assert created.status_code == 201
    response = client.post(
        f"/api/v1/applications/{application_id}/evidence/{created.json()['id']}/renewals",
        headers=headers,
        json={
            "title": "Certificate",
            "category": "other",
            "expires_on": str(date.today() - timedelta(days=1)),
        },
    )
    assert response.status_code == 422
