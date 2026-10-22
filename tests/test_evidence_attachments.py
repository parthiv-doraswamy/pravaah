"""Security and lifecycle tests for private evidence file attachments."""

import hashlib

from app.auth.security import hash_password
from app.models.core import Application, Institution, User


def _setup(session_factory, email: str, role: str = "institution_user"):
    with session_factory() as db:
        institution = Institution(
            name=f"Attachment Institution {email}",
            code=f"ATT-{email.split('@')[0].upper()}",
            region_code="ATT-REGION",
        )
        db.add(institution)
        db.flush()
        user = User(
            email=email,
            full_name="Attachment Test User",
            role=role,
            password_hash=hash_password("Test-password-123!"),
            institution_id=institution.id,
        )
        application = Application(
            application_number=f"ATT-{email.split('@')[0].upper()}",
            title="Attachment test application",
            status="under_scrutiny",
            institution_id=institution.id,
        )
        db.add_all([user, application])
        db.commit()
        return application.id


def _login(client, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Test-password-123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_evidence(client, headers, application_id):
    response = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={
            "title": "Synthetic safety certificate",
            "category": "safety_certificate",
            "reference_number": "DEMO-SAFE-01",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_authorized_user_can_upload_list_and_download_pdf(api_client_and_sessions, tmp_path, monkeypatch):
    from app.core.config import Settings
    import app.api.v1.routes.evidence as evidence_routes

    client, session_factory = api_client_and_sessions
    application_id = _setup(session_factory, "upload-owner@example.test")
    headers = {"Authorization": f"Bearer {_login(client, 'upload-owner@example.test')}"}
    evidence_id = _create_evidence(client, headers, application_id)
    monkeypatch.setattr(
        evidence_routes,
        "get_settings",
        lambda: Settings(evidence_storage_dir=str(tmp_path), evidence_max_upload_bytes=1024),
    )
    content = b"%PDF-1.7\nsynthetic demo evidence\n%%EOF"
    uploaded = client.post(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
        headers=headers,
        files={"file": ("safety-demo.pdf", content, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()
    assert attachment["original_filename"] == "safety-demo.pdf"
    assert attachment["content_type"] == "application/pdf"
    assert attachment["size_bytes"] == len(content)
    assert attachment["sha256_hex"] == hashlib.sha256(content).hexdigest()

    listed = client.get(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
        headers=headers,
    )
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [attachment["id"]]

    downloaded = client.get(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments/{attachment['id']}/download",
        headers=headers,
    )
    assert downloaded.status_code == 200
    assert downloaded.content == content
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert "private" in downloaded.headers["cache-control"]


def test_upload_rejects_mismatched_content_and_oversized_files(api_client_and_sessions, tmp_path, monkeypatch):
    from app.core.config import Settings
    import app.api.v1.routes.evidence as evidence_routes

    client, session_factory = api_client_and_sessions
    application_id = _setup(session_factory, "upload-validation@example.test")
    headers = {"Authorization": f"Bearer {_login(client, 'upload-validation@example.test')}"}
    evidence_id = _create_evidence(client, headers, application_id)
    monkeypatch.setattr(
        evidence_routes,
        "get_settings",
        lambda: Settings(evidence_storage_dir=str(tmp_path), evidence_max_upload_bytes=12),
    )
    mismatch = client.post(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
        headers=headers,
        files={"file": ("not-really.pdf", b"this is not a PDF", "application/pdf")},
    )
    assert mismatch.status_code == 413

    monkeypatch.setattr(
        evidence_routes,
        "get_settings",
        lambda: Settings(evidence_storage_dir=str(tmp_path), evidence_max_upload_bytes=1024),
    )
    mismatch = client.post(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
        headers=headers,
        files={"file": ("not-really.pdf", b"plain text, not a PDF", "application/pdf")},
    )
    assert mismatch.status_code == 415


def test_upload_requires_write_role_and_download_is_application_scoped(api_client_and_sessions, tmp_path, monkeypatch):
    from app.core.config import Settings
    import app.api.v1.routes.evidence as evidence_routes

    client, session_factory = api_client_and_sessions
    application_id = _setup(session_factory, "upload-scope-owner@example.test")
    headers = {"Authorization": f"Bearer {_login(client, 'upload-scope-owner@example.test')}"}
    evidence_id = _create_evidence(client, headers, application_id)
    monkeypatch.setattr(
        evidence_routes,
        "get_settings",
        lambda: Settings(evidence_storage_dir=str(tmp_path), evidence_max_upload_bytes=1024),
    )
    content = b"%PDF-1.4\nprivate file\n%%EOF"
    uploaded = client.post(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
        headers=headers,
        files={"file": ("private.pdf", content, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]

    other_application = _setup(session_factory, "upload-scope-other@example.test")
    other_headers = {"Authorization": f"Bearer {_login(client, 'upload-scope-other@example.test')}"}
    forbidden = client.get(
        f"/api/v1/applications/{other_application}/evidence/{evidence_id}/attachments/{attachment_id}/download",
        headers=other_headers,
    )
    assert forbidden.status_code == 404

    reviewer_app = _setup(session_factory, "upload-readonly@example.test", role="citizen")
    readonly_headers = {"Authorization": f"Bearer {_login(client, 'upload-readonly@example.test')}"}
    readonly_evidence = _create_evidence(client, readonly_headers, reviewer_app)
    denied = client.post(
        f"/api/v1/applications/{reviewer_app}/evidence/{readonly_evidence}/attachments",
        headers=readonly_headers,
        files={"file": ("demo.pdf", content, "application/pdf")},
    )
    assert denied.status_code == 403
