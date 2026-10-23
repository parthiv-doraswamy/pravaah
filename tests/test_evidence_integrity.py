"""Regression tests for detecting corrupted evidence attachments at download time."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.auth.security import hash_password
from app.core.config import Settings
from app.models.core import Application, Institution, User
from app.models.evidence_attachment import EvidenceAttachment
import app.api.v1.routes.evidence as evidence_routes


def test_download_blocks_attachment_when_stored_bytes_change(api_client_and_sessions, tmp_path, monkeypatch):
    client, session_factory = api_client_and_sessions
    email = "integrity-check@example.test"
    with session_factory() as db:
        institution = Institution(
            name="Integrity Test Institution", code="INTEGRITY-01", region_code="INTEGRITY-REGION"
        )
        db.add(institution)
        db.flush()
        user = User(
            email=email,
            full_name="Integrity Test User",
            role="institution_user",
            password_hash=hash_password("Test-password-123!"),
            institution_id=institution.id,
        )
        application = Application(
            application_number="PVH-INTEGRITY-01",
            title="Synthetic integrity test case",
            status="under_scrutiny",
            institution_id=institution.id,
        )
        db.add_all([user, application])
        db.commit()
        application_id = application.id

    login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "Test-password-123!"
    })
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    evidence_response = client.post(
        f"/api/v1/applications/{application_id}/evidence",
        headers=headers,
        json={"title": "Synthetic certificate", "category": "safety_certificate"},
    )
    assert evidence_response.status_code == 201, evidence_response.text
    evidence_id = evidence_response.json()["id"]

    monkeypatch.setattr(
        evidence_routes,
        "get_settings",
        lambda: Settings(evidence_storage_dir=str(tmp_path), evidence_max_upload_bytes=1024),
    )
    content = b"%PDF-1.4\noriginal synthetic evidence\n%%EOF"
    uploaded = client.post(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
        headers=headers,
        files={"file": ("certificate.pdf", content, "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment = uploaded.json()
    # The API intentionally omits private storage keys from its response schema.
    with session_factory() as db:
        stored_attachment = db.scalar(
            select(EvidenceAttachment).where(EvidenceAttachment.id == UUID(attachment["id"]))
        )
        assert stored_attachment is not None
        storage_key = stored_attachment.storage_key
    storage_path = tmp_path / storage_key[:2] / storage_key
    assert storage_path.is_file()

    # Simulate disk corruption after upload; metadata still contains the original hash and size.
    storage_path.write_bytes(b"%PDF-1.4\nmodified synthetic evidence\n%%EOF")
    download = client.get(
        f"/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments/{attachment['id']}/download",
        headers=headers,
    )
    assert download.status_code == 409
    assert "integrity verification failed" in download.json()["detail"].lower()
