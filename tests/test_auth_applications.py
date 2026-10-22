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
