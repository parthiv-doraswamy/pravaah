"""Integration tests for authentication and institution-level data isolation."""

from app.auth.security import hash_password
from app.models.core import Application, Institution, User


def create_institution_user(session_factory, *, email: str, code: str, name: str):
    with session_factory() as db:
        institution = Institution(name=f"Institution {name}", code=code, region_code="REGION-A")
        db.add(institution)
        db.flush()
        user = User(
            email=email,
            full_name=name,
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=institution.id,
        )
        db.add(user)
        db.commit()
        return institution.id, user.id


def test_login_and_current_user_profile(api_client_and_sessions) -> None:
    client, session_factory = api_client_and_sessions
    create_institution_user(
        session_factory, email="user@example.test", code="INST-A", name="Demo User"
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.test", "password": "Test-password-123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["email"] == "user@example.test"
    assert profile.json()["role"] == "institution_user"


def test_institution_user_only_sees_own_applications(api_client_and_sessions) -> None:
    client, session_factory = api_client_and_sessions
    institution_a, _ = create_institution_user(
        session_factory, email="a@example.test", code="INST-A", name="User A"
    )
    institution_b, _ = create_institution_user(
        session_factory, email="b@example.test", code="INST-B", name="User B"
    )
    with session_factory() as db:
        db.add_all(
            [
                Application(application_number="PVH-TEST-A", title="Visible case", status="draft", institution_id=institution_a),
                Application(application_number="PVH-TEST-B", title="Private case", status="draft", institution_id=institution_b),
            ]
        )
        db.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.test", "password": "Test-password-123!"},
    )
    token = login.json()["access_token"]
    response = client.get("/api/v1/applications", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert [item["application_number"] for item in response.json()["items"]] == ["PVH-TEST-A"]


def test_application_registry_requires_authentication(api_client_and_sessions) -> None:
    client, _ = api_client_and_sessions
    response = client.get("/api/v1/applications")
    assert response.status_code == 401


def test_wrong_password_is_rejected(api_client_and_sessions) -> None:
    client, session_factory = api_client_and_sessions
    create_institution_user(
        session_factory, email="wrong-password@example.test", code="INST-C", name="User C"
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "wrong-password@example.test", "password": "not-the-password"},
    )
    assert response.status_code == 401


def test_institution_user_can_create_draft_for_own_institution(api_client_and_sessions) -> None:
    client, session_factory = api_client_and_sessions
    institution_id, _ = create_institution_user(
        session_factory, email="creator@example.test", code="INST-D", name="Creator"
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "creator@example.test", "password": "Test-password-123!"},
    )
    token = login.json()["access_token"]

    response = client.post(
        "/api/v1/applications",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "New programme proposal", "summary": "Synthetic integration-test case"},
    )

    assert response.status_code == 201
    assert response.json()["status"] == "draft"
    assert response.json()["institution_id"] == str(institution_id)
    assert response.json()["application_number"].startswith("PVH-")



def test_institution_cannot_read_another_institutions_case_or_evidence(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    institution_a, _ = create_institution_user(
        session_factory, email="scope-owner@example.test", code="SCOPE-A", name="Scope Owner"
    )
    institution_b, _ = create_institution_user(
        session_factory, email="scope-other@example.test", code="SCOPE-B", name="Scope Other"
    )
    with session_factory() as db:
        private_case = Application(
            application_number="PVH-SCOPE-PRIVATE",
            title="Private institution case",
            status="draft",
            institution_id=institution_b,
        )
        db.add(private_case)
        db.commit()
        private_case_id = private_case.id

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "scope-owner@example.test", "password": "Test-password-123!"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    case_response = client.get(f"/api/v1/applications/{private_case_id}", headers=headers)
    assert case_response.status_code == 404

    evidence_response = client.get(
        f"/api/v1/applications/{private_case_id}/evidence",
        headers=headers,
    )
    assert evidence_response.status_code == 404

    transition_response = client.post(
        f"/api/v1/applications/{private_case_id}/transitions",
        headers=headers,
        json={
            "expected_status": "draft",
            "target_status": "submitted",
            "reason": "Must not cross institution boundaries",
        },
    )
    assert transition_response.status_code == 404

    own_case = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"title": "Owner institution case", "summary": "Scope control test"},
    )
    assert own_case.status_code == 201
    assert own_case.json()["institution_id"] == str(institution_a)



def test_regional_officer_cannot_access_applications_outside_assigned_region(api_client_and_sessions):
    client, session_factory = api_client_and_sessions
    region_a, _ = create_institution_user(
        session_factory, email="region-a-owner@example.test", code="REG-A-OWNER", name="Region A Owner"
    )
    region_b, _ = create_institution_user(
        session_factory, email="region-b-owner@example.test", code="REG-B-OWNER", name="Region B Owner"
    )
    with session_factory() as db:
        region_b_institution = db.get(Institution, region_b)
        region_b_institution.region_code = "REGION-B"
        regional_user = User(
            email="regional-reviewer@example.test",
            full_name="Regional Reviewer",
            role="regional_officer",
            password_hash=hash_password("Test-password-123!"),
            institution_id=region_a,
        )
        foreign_case = Application(
            application_number="PVH-REGION-B-PRIVATE",
            title="Region B private case",
            status="submitted",
            institution_id=region_b,
        )
        db.add_all([regional_user, foreign_case])
        db.commit()
        foreign_case_id = foreign_case.id

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "regional-reviewer@example.test", "password": "Test-password-123!"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    registry = client.get("/api/v1/applications", headers=headers)
    assert registry.status_code == 200
    assert all(item["institution_id"] != str(region_b) for item in registry.json()["items"])

    detail = client.get(f"/api/v1/applications/{foreign_case_id}", headers=headers)
    assert detail.status_code == 404
    timeline = client.get(f"/api/v1/applications/{foreign_case_id}/events", headers=headers)
    assert timeline.status_code == 404
