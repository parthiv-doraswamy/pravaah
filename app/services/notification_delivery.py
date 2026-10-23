"""Optional SMTP delivery with capped exponential retries and durable attempt logs."""

import os
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.core import User
from app.models.notification import NotificationRecord
from app.models.notification_attempt import NotificationAttempt

DeliveryTransport = Callable[[str, str, str], None]
MAX_BACKOFF_MINUTES = 60


class DeliveryNotConfigured(RuntimeError):
    """Raised when SMTP delivery is requested without SMTP settings."""


def smtp_is_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_FROM"))


def send_email(recipient: str, subject: str, body: str) -> None:
    """Send one email using environment-configured SMTP; no credentials are stored in source."""
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not host or not sender:
        raise DeliveryNotConfigured("SMTP_HOST and SMTP_FROM must be configured")
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as client:
        if use_tls:
            client.starttls()
        if username:
            client.login(username, password or "")
        client.send_message(message)


def process_due_notifications(
    db: Session,
    *,
    transport: DeliveryTransport | None = None,
    now: datetime | None = None,
    enabled: bool | None = None,
    limit: int = 50,
) -> dict[str, int | str]:
    """Attempt configured email deliveries; keep queued in-app records when SMTP is absent."""
    run_at = now or datetime.now(UTC)
    delivery_enabled = smtp_is_configured() if enabled is None else enabled
    if not delivery_enabled:
        due_count = db.scalar(
            select(func.count(NotificationRecord.id)).where(
                NotificationRecord.delivery_status == "pending",
                or_(NotificationRecord.next_attempt_at.is_(None), NotificationRecord.next_attempt_at <= run_at),
            )
        )
        return {
            "attempted": 0,
            "sent": 0,
            "failed": 0,
            "deferred": int(due_count or 0),
            "detail": "SMTP is not configured; in-app notifications remain available and email attempts are deferred.",
        }

    deliver = transport or send_email
    records = db.execute(
        select(NotificationRecord, User)
        .join(User, User.id == NotificationRecord.recipient_user_id)
        .where(
            NotificationRecord.delivery_status == "pending",
            or_(NotificationRecord.next_attempt_at.is_(None), NotificationRecord.next_attempt_at <= run_at),
            NotificationRecord.attempt_count < NotificationRecord.max_attempts,
        )
        .order_by(NotificationRecord.created_at.asc())
        .limit(min(max(limit, 1), 200))
        .with_for_update(of=NotificationRecord, skip_locked=True)
    ).all()

    sent = 0
    failed = 0
    skipped_inactive = 0
    attempted = 0
    for notification, recipient in records:
        if not recipient.is_active:
            notification.delivery_status = "failed"
            notification.last_error = "Recipient account is inactive; email delivery was not attempted."
            notification.next_attempt_at = None
            notification.updated_at = run_at
            skipped_inactive += 1
            failed += 1
            continue

        attempted += 1
        attempt_number = notification.attempt_count + 1
        next_attempt: datetime | None = None
        try:
            deliver(recipient.email, notification.title, notification.message)
            notification.delivery_status = "sent"
            notification.sent_at = run_at
            notification.last_error = None
            outcome = "sent"
            sent += 1
        except Exception as error:
            # Provider exception text can contain hostnames, addresses, or credentials.
            # Persist only the exception class and a fixed message; keep details out of audit rows.
            message = f"Email delivery failed ({type(error).__name__}); provider details redacted."
            notification.last_error = message
            if attempt_number >= notification.max_attempts:
                notification.delivery_status = "failed"
                notification.next_attempt_at = None
                outcome = "failed"
                failed += 1
            else:
                delay_minutes = min(5 * (2 ** (attempt_number - 1)), MAX_BACKOFF_MINUTES)
                next_attempt = run_at + timedelta(minutes=delay_minutes)
                notification.delivery_status = "pending"
                notification.next_attempt_at = next_attempt
                outcome = "retry_scheduled"

        notification.attempt_count = attempt_number
        notification.updated_at = run_at
        db.add(NotificationAttempt(
            notification_id=notification.id,
            attempt_number=attempt_number,
            channel="email",
            outcome=outcome,
            error_message=notification.last_error if outcome != "sent" else None,
            attempted_at=run_at,
            next_attempt_at=next_attempt,
        ))

    db.commit()
    return {
        "processed": len(records),
        "attempted": attempted,
        "sent": sent,
        "failed": failed,
        "skipped_inactive_recipients": skipped_inactive,
        "deferred": 0,
        "detail": "Delivery attempt results were recorded.",
    }
