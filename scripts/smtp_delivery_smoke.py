"""Verify SMTP delivery end-to-end against a disposable Mailpit sink.

The script uses synthetic records and is intended for CI only. Mailpit accepts
SMTP locally and stores messages for inspection; no external mailbox is contacted.
"""
from __future__ import annotations

import os
import time
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

from app.auth.security import hash_password
from app.db.session import get_session_factory
from app.models.core import Application, Institution, User
from app.models.notification import NotificationRecord
from app.models.notification_attempt import NotificationAttempt
from app.services.notification_delivery import process_due_notifications

MAILPIT_API = os.getenv("MAILPIT_API", "http://127.0.0.1:8025")

def wait_for_mailpit(timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "Mailpit did not respond"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{MAILPIT_API}/api/v1/messages", timeout=3)
            if response.status_code == 200:
                return
            last_error = f"Mailpit returned HTTP {response.status_code}"
        except httpx.HTTPError as error:
            last_error = type(error).__name__
        time.sleep(1)
    raise RuntimeError(f"SMTP test sink unavailable: {last_error}")


def create_pending_notification() -> tuple[str, str, str]:
    suffix = uuid4().hex[:10]
    email = f"smtp-test-{suffix}@example.test"
    subject = f"PRAVAAH SMTP CI {suffix}"
    body = f"Synthetic SMTP delivery verification {suffix}"

    with get_session_factory()() as db:
        institution = Institution(
            name=f"SMTP CI Institution {suffix}",
            code=f"SMTP-{suffix.upper()}",
            region_code="SMTP-CI",
        )
        db.add(institution)
        db.flush()
        user = User(
            email=email,
            full_name="Synthetic SMTP Recipient",
            role="institution_user",
            institution_id=institution.id,
            password_hash=hash_password("SMTP-CI-Only-Password-2026!"),
            is_active=True,
        )
        application = Application(
            application_number=f"PVH-SMTP-{suffix.upper()}",
            title="Synthetic SMTP delivery case",
            status="under_scrutiny",
            institution_id=institution.id,
        )
        db.add_all([user, application])
        db.flush()
        notification = NotificationRecord(
            recipient_user_id=user.id,
            application_id=application.id,
            evidence_id=None,
            dedupe_key=f"smtp-ci-{suffix}",
            notification_type="smtp_ci_test",
            title=subject,
            message=body,
            severity="info",
            delivery_status="pending",
            attempt_count=0,
            max_attempts=3,
            next_attempt_at=None,
        )
        db.add(notification)
        db.commit()
        return str(notification.id), email, subject


def main() -> None:
    if os.getenv("APP_ENV", "").lower() != "test":
        raise RuntimeError("Refusing to run SMTP smoke test unless APP_ENV=test")
    if os.getenv("SMTP_HOST") != "127.0.0.1" or os.getenv("SMTP_PORT") != "1025":
        raise RuntimeError("Refusing to run SMTP smoke test unless SMTP targets local Mailpit")

    wait_for_mailpit()
    notification_id, recipient, subject = create_pending_notification()

    with get_session_factory()() as db:
        result = process_due_notifications(db, enabled=True)
    assert result["attempted"] == 1, f"Expected one SMTP attempt; got {result}"
    assert result["sent"] == 1, f"SMTP delivery did not succeed: {result}"

    deadline = time.monotonic() + 30
    matching_message = None
    while time.monotonic() < deadline:
        response = httpx.get(f"{MAILPIT_API}/api/v1/messages", timeout=5)
        response.raise_for_status()
        messages = response.json().get("messages", [])
        for message in messages:
            to_addresses = [
                item.get("Address", "").lower() for item in message.get("To", [])
            ]
            if message.get("Subject") == subject and recipient.lower() in to_addresses:
                matching_message = message
                break
        if matching_message:
            break
        time.sleep(1)

    assert matching_message is not None, "Expected message was not received by the SMTP sink"
    with get_session_factory()() as db:
        notification = db.get(NotificationRecord, UUID(notification_id))
        assert notification is not None
        assert notification.delivery_status == "sent"
        assert notification.attempt_count == 1
        attempts = db.scalars(
            select(NotificationAttempt).where(
                NotificationAttempt.notification_id == notification.id
            )
        ).all()
        assert len(attempts) == 1
        assert attempts[0].outcome == "sent"

        # A second worker cycle must not send a duplicate after the record is marked sent.
        repeat = process_due_notifications(db, enabled=True)
        assert repeat["attempted"] == 0
        assert repeat["sent"] == 0

    print(
        "SMTP smoke passed: local SMTP handshake, message accepted by Mailpit, "
        "delivery state and attempt audit persisted, and no duplicate on repeat cycle."
    )


if __name__ == "__main__":
    main()
