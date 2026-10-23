"""End-to-end policy registry, activation, and transition API integration."""

from datetime import UTC, datetime, timedelta

from app.auth.security import hash_password
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence


def _login(client, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_policy_api_create_activate_and_enforce_prerequisites(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    password = "Test-password-123!"
    with session_factory() as db:
        institution = Institution(
            name="Policy API Integration College",
            code="PAPI-001",
            region_code="PAPI-REGION",
        )
        db.add(institution)
        db.flush()
        policy_admin = User(
            email="policy-api-admin@example.test",
            full_name="Policy API Admin",
            role="policy_admin",
            password_hash=hash_password(password),
        )
        institution_user = User(
            email="policy-api-institution@example.test",
            full_name="Policy API Institution User",
            role="institution_user",
            institution_id=institution.id,
            password_hash=hash_password(password),
        )
        scrutiny_officer = User(
            email="policy-api-reviewer@example.test",
            full_name="Policy API Reviewer",
            role="scrutiny_officer",
            password_hash=hash_password(password),
        )
        application = Application(
            application_number="PVH-PAPI-001",
            title="Policy API integration case",
            summary="Synthetic integration test",
            status="draft",
            institution_id=institution.id,
        )
        db.add_all([policy_admin, institution_user, scrutiny_officer, application])
        db.commit()
        db.refresh(application)
        application_id = str(application.id)
        application_uuid = application.id

    admin_headers = _login(client, "policy-api-admin@example.test", password)
    institution_headers = _login(client, "policy-api-institution@example.test", password)
    reviewer_headers = _login(client, "policy-api-reviewer@example.test", password)

    policy_response = client.post(
        "/api/v1/applications/policies/registry",
        headers=admin_headers,
        json={
            "policy_key": "application_workflow",
            "version": 1,
            "title": "Synthetic API integration policy",
            "description": "Test-only policy; not official AICTE guidance.",
            "effective_from": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "source_label": "Synthetic API integration test",
            "rules_schema_version": 1,
            "rules": {
                "transitions": [
                    {
                        "from_status": "draft",
                        "to_status": "submitted",
                        "allowed_roles": ["institution_user"],
                    },
                    {
                        "from_status": "submitted",
                        "to_status": "under_scrutiny",
                        "allowed_roles": ["scrutiny_officer"],
                    },
                ],
                "prerequisites": [
                    {
                        "status": "submitted",
                        "required_fields": ["title", "institution_id"],
                        "required_evidence_categories": ["identity_document"],
                    }
                ],
            },
        },
    )
    assert policy_response.status_code == 201
    assert policy_response.json()["is_active"] is False

    transition_url = f"/api/v1/applications/{application_id}/transitions"

    forbidden_activation = client.post(
        "/api/v1/applications/policies/registry/application_workflow/1/activate",
        headers=reviewer_headers,
    )
    assert forbidden_activation.status_code == 403

    activation = client.post(
        "/api/v1/applications/policies/registry/application_workflow/1/activate",
        headers=admin_headers,
    )
    assert activation.status_code == 200
    assert activation.json()["is_active"] is True

    blocked = client.post(
        transition_url,
        headers=institution_headers,
        json={"target_status": "submitted", "expected_status": "draft"},
    )
    assert blocked.status_code == 409
    assert "missing_evidence_categories" in str(blocked.json()["detail"])

    with session_factory() as db:
        db.add(ApplicationEvidence(
            application_id=application_uuid,
            title="Identity document",
            category="identity_document",
        ))
        db.commit()

    submitted = client.post(
        transition_url,
        headers=institution_headers,
        json={"target_status": "submitted", "expected_status": "draft"},
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "submitted"

    reviewed = client.post(
        transition_url,
        headers=reviewer_headers,
        json={"target_status": "under_scrutiny", "expected_status": "submitted"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "under_scrutiny"
