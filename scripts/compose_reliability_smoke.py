"""Exercise a clean Docker Compose stack, idempotent seeding, and upload persistence.

This script is intended for the dedicated CI Compose project only. It uses synthetic
records and a local-only database URL; it never targets hosted services.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from uuid import UUID

import httpx
from sqlalchemy import func, select

from app.db.session import get_session_factory
from app.models.core import Application, Institution, User
from app.models.evidence_attachment import EvidenceAttachment
from app.models.workflow import ApplicationEvent, PolicyVersion

PROJECT = "pravaah-reliability-ci"
BASE_URL = os.getenv("PRAVAAH_BASE_URL", "http://127.0.0.1:8000")
PASSWORD = os.getenv("DEMO_USER_PASSWORD", "")
DEMO_APPLICATIONS = (
    "PVH-DEMO-1001",
    "PVH-DEMO-1002",
    "PVH-DEMO-2001",
)
DEMO_USERS = (
    "demo.institution@example.test",
    "demo.reviewer@example.test",
    "demo.bureau@example.test",
    "demo.authority@example.test",
)


def compose(*args: str) -> None:
    subprocess.run(
        ["docker", "compose", "--project-name", PROJECT, *args],
        check=True,
        text=True,
    )


def wait_until_ready(timeout_seconds: int = 180) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "API did not respond"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{BASE_URL}/health/ready", timeout=3)
            if response.status_code == 200:
                return
            last_error = f"readiness returned HTTP {response.status_code}"
        except httpx.HTTPError as error:
            last_error = type(error).__name__
        time.sleep(2)
    raise RuntimeError(f"API did not become ready within {timeout_seconds}s: {last_error}")


def assert_seed_is_idempotent() -> None:
    if not PASSWORD or len(PASSWORD) < 12:
        raise RuntimeError("A local-only DEMO_USER_PASSWORD of at least 12 characters is required")

    # The API startup already seeds once. Re-run the same command twice to prove
    # that repeated startup/seed operations do not duplicate the synthetic records.
    compose("exec", "-T", "api", "python", "-m", "scripts.seed_demo")
    compose("exec", "-T", "api", "python", "-m", "scripts.seed_demo")

    with get_session_factory()() as db:
        for number in DEMO_APPLICATIONS:
            count = db.scalar(
                select(func.count()).select_from(Application).where(
                    Application.application_number == number
                )
            )
            assert count == 1, f"Expected one seeded application {number}; found {count}"

            application = db.scalar(
                select(Application).where(Application.application_number == number)
            )
            seed_events = db.scalar(
                select(func.count()).select_from(ApplicationEvent).where(
                    ApplicationEvent.application_id == application.id,
                    ApplicationEvent.event_type == "demo_case_seeded",
                )
            )
            assert seed_events == 1, (
                f"Expected one seed audit event for {number}; found {seed_events}"
            )

        for email in DEMO_USERS:
            count = db.scalar(
                select(func.count()).select_from(User).where(User.email == email)
            )
            assert count == 1, f"Expected one demo account for {email}; found {count}"

        for code in ("DEMO-001", "DEMO-002"):
            count = db.scalar(
                select(func.count()).select_from(Institution).where(Institution.code == code)
            )
            assert count == 1, f"Expected one demo institution {code}; found {count}"

        for key in ("APPLICATION_COMPLETENESS", "SCRUTINY_TIMELINE", "EVIDENCE_EXPIRY"):
            count = db.scalar(
                select(func.count()).select_from(PolicyVersion).where(
                    PolicyVersion.policy_key == key,
                    PolicyVersion.version == 1,
                )
            )
            assert count == 1, f"Expected one version 1 policy for {key}; found {count}"


def login(client: httpx.Client) -> dict[str, str]:
    response = client.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"email": "demo.institution@example.test", "password": PASSWORD},
    )
    assert response.status_code == 200, f"Demo login failed: HTTP {response.status_code}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_and_verify_attachment() -> tuple[str, str, str, bytes]:
    pdf = b"%PDF-1.7\nPRAVAAH compose reliability smoke test\n%%EOF\n"
    expected_hash = hashlib.sha256(pdf).hexdigest()

    with httpx.Client(timeout=20) as client:
        headers = login(client)
        registry = client.get(
            f"{BASE_URL}/api/v1/applications",
            params={"page": 1, "page_size": 100},
            headers=headers,
        )
        assert registry.status_code == 200, "Could not list applications"
        matches = [
            item for item in registry.json()["items"]
            if item["application_number"] == DEMO_APPLICATIONS[0]
        ]
        assert len(matches) == 1, "Seeded demo application must be unique and visible"
        application_id = matches[0]["id"]

        evidence_response = client.post(
            f"{BASE_URL}/api/v1/applications/{application_id}/evidence",
            headers=headers,
            json={
                "title": "Compose restart persistence certificate",
                "category": "safety_certificate",
                "reference_number": "COMPOSE-RELIABILITY-001",
                "notes": "Synthetic CI-only record; not an official certificate.",
            },
        )
        assert evidence_response.status_code == 201, "Could not register smoke evidence"
        evidence_id = evidence_response.json()["id"]

        upload = client.post(
            f"{BASE_URL}/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
            headers=headers,
            files={"file": ("compose-smoke.pdf", pdf, "application/pdf")},
        )
        assert upload.status_code == 201, (
            f"Evidence upload failed with HTTP {upload.status_code}"
        )
        attachment = upload.json()
        assert attachment["sha256_hex"] == expected_hash
        assert attachment["size_bytes"] == len(pdf)

        downloaded = client.get(
            f"{BASE_URL}/api/v1/applications/{application_id}/evidence/"
            f"{evidence_id}/attachments/{attachment['id']}/download",
            headers=headers,
        )
        assert downloaded.status_code == 200
        assert downloaded.content == pdf
        assert hashlib.sha256(downloaded.content).hexdigest() == expected_hash

        verification = client.get(
            f"{BASE_URL}/api/v1/applications/{application_id}/events/verify",
            headers=headers,
        )
        assert verification.status_code == 200
        assert verification.json()["valid"] is True

    return application_id, evidence_id, attachment["id"], pdf


def verify_attachment_survived_restart(
    application_id: str,
    evidence_id: str,
    attachment_id: str,
    expected_bytes: bytes,
) -> None:
    wait_until_ready()
    with httpx.Client(timeout=20) as client:
        headers = login(client)
        listing = client.get(
            f"{BASE_URL}/api/v1/applications/{application_id}/evidence/{evidence_id}/attachments",
            headers=headers,
        )
        assert listing.status_code == 200
        assert any(item["id"] == attachment_id for item in listing.json()), (
            "Attachment metadata was not preserved after API restart"
        )

        download = client.get(
            f"{BASE_URL}/api/v1/applications/{application_id}/evidence/"
            f"{evidence_id}/attachments/{attachment_id}/download",
            headers=headers,
        )
        assert download.status_code == 200, "Attachment bytes unavailable after API restart"
        assert download.content == expected_bytes, "Attachment bytes changed after API restart"

        verification = client.get(
            f"{BASE_URL}/api/v1/applications/{application_id}/events/verify",
            headers=headers,
        )
        assert verification.status_code == 200
        assert verification.json()["valid"] is True

    with get_session_factory()() as db:
        attachment_count = db.scalar(
            select(func.count()).select_from(EvidenceAttachment).where(
                EvidenceAttachment.id == UUID(attachment_id),
                EvidenceAttachment.application_id == UUID(application_id),
                EvidenceAttachment.evidence_id == UUID(evidence_id),
            )
        )
        assert attachment_count == 1, "Attachment database row was not preserved"

        for number in DEMO_APPLICATIONS:
            count = db.scalar(
                select(func.count()).select_from(Application).where(
                    Application.application_number == number
                )
            )
            assert count == 1, f"Restart duplicated seeded application {number}"


def main() -> None:
    # Fail closed unless the host-side smoke script is pointed at the known local
    # Compose database. This prevents accidental use against hosted or shared data.
    database_url = os.getenv("DATABASE_URL", "")
    if database_url != "postgresql+psycopg://pravaah:pravaah@127.0.0.1:5432/pravaah":
        raise RuntimeError("Refusing to run: DATABASE_URL is not the dedicated local CI Compose DB")
    if os.getenv("APP_ENV", "").lower() != "development":
        raise RuntimeError("Refusing to run unless APP_ENV=development")

    wait_until_ready()
    assert_seed_is_idempotent()
    application_id, evidence_id, attachment_id, pdf = create_and_verify_attachment()

    # Restart only the API container. PostgreSQL and the private uploads volume
    # remain running, matching the intended service-recovery scenario.
    compose("restart", "api")
    verify_attachment_survived_restart(application_id, evidence_id, attachment_id, pdf)

    print(
        "Compose reliability smoke passed: clean startup, migrations, idempotent demo seed, "
        "private attachment download, API restart persistence, and valid audit chain."
    )


if __name__ == "__main__":
    main()
