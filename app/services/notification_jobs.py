"""Scheduled, idempotent expiry notification and escalation jobs."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.escalation import ComplianceEscalation
from app.models.notification import NotificationRecord
from app.services.workflow import append_event

ESCALATION_AFTER_DAYS = 7


def expiry_severity(expires_on: date, today: date) -> tuple[str, int] | None:
    days = (expires_on - today).days
    if days < 0:
        return "expired", days
    if days <= 1:
        return "urgent", days
    if days <= 7:
        return "warning", days
    if days <= 30:
        return "upcoming", days
    return None


def run_expiry_monitoring(db: Session, today: date | None = None) -> dict[str, int | str]:
    """Queue deduplicated in-app reminders and open escalations for long-expired evidence."""
    run_date = today or datetime.now(UTC).date()
    now = datetime.now(UTC)
    rows = db.execute(
        select(ApplicationEvidence, Application, User)
        .join(Application, Application.id == ApplicationEvidence.application_id)
        .join(User, User.institution_id == Application.institution_id)
        .where(
            User.role == "institution_user",
            User.is_active.is_(True),
            ApplicationEvidence.expires_on.is_not(None),
        )
        .order_by(ApplicationEvidence.expires_on.asc())
    ).all()

    queued = 0
    skipped = 0
    escalated = 0
    audited: set[tuple[str, str]] = set()

    for evidence, application, recipient in rows:
        classified = expiry_severity(evidence.expires_on, run_date)
        if classified is None:
            continue
        severity, days = classified
        day_text = "expired" if days < 0 else (
            "expires today" if days == 0 else f"expires in {days} day{'s' if days != 1 else ''}"
        )
        notification_key = (
            f"expiry:{evidence.id}:{evidence.expires_on.isoformat()}:{severity}:{recipient.id}"
        )
        exists = db.scalar(select(NotificationRecord.id).where(NotificationRecord.dedupe_key == notification_key))
        if exists is None:
            db.add(NotificationRecord(
                recipient_user_id=recipient.id,
                application_id=application.id,
                evidence_id=evidence.id,
                dedupe_key=notification_key,
                notification_type="evidence_expiry",
                title=f"Evidence {day_text}: {evidence.title}",
                message=f"{application.application_number} — {application.title}. {evidence.title} {day_text}. Review the record and arrange any required follow-up.",
                severity=severity,
                delivery_status="pending",
                attempt_count=0,
                max_attempts=5,
                next_attempt_at=now,
            ))
            db.flush()
            queued += 1
            key = (str(evidence.id), "expiry_notification_queued")
            if key not in audited:
                append_event(
                    db, application_id=application.id, event_type="expiry_notification_queued",
                    from_status=application.status, to_status=application.status, actor_user_id=None,
                    metadata={"evidence_id": str(evidence.id), "severity": severity,
                              "days_remaining": days, "notification_date": run_date.isoformat(),
                              "source": "scheduled_worker"},
                )
                audited.add(key)
        else:
            skipped += 1

        if days < -ESCALATION_AFTER_DAYS:
            escalation_key = f"expired:{evidence.id}:{evidence.expires_on.isoformat()}:after-{ESCALATION_AFTER_DAYS}d"
            existing_escalation = db.scalar(
                select(ComplianceEscalation.id).where(ComplianceEscalation.dedupe_key == escalation_key)
            )
            if existing_escalation is None:
                escalation = ComplianceEscalation(
                    dedupe_key=escalation_key,
                    application_id=application.id,
                    evidence_id=evidence.id,
                    escalation_type="evidence_expired",
                    status="open",
                    severity="high",
                    summary=f"{evidence.title} expired on {evidence.expires_on.isoformat()} and remains expired beyond the synthetic {ESCALATION_AFTER_DAYS}-day escalation threshold.",
                    triggered_at=now,
                )
                db.add(escalation)
                db.flush()
                escalated += 1
                append_event(
                    db, application_id=application.id, event_type="compliance_escalation_opened",
                    from_status=application.status, to_status=application.status, actor_user_id=None,
                    metadata={"escalation_id": str(escalation.id), "evidence_id": str(evidence.id),
                              "severity": "high", "days_expired": abs(days),
                              "threshold_days": ESCALATION_AFTER_DAYS, "source": "scheduled_worker"},
                )
                for escalation_recipient in [recipient]:
                    escalation_notification_key = f"escalation:{escalation.id}:{escalation_recipient.id}"
                    db.add(NotificationRecord(
                        recipient_user_id=escalation_recipient.id,
                        application_id=application.id,
                        evidence_id=evidence.id,
                        dedupe_key=escalation_notification_key,
                        notification_type="compliance_escalation",
                        title=f"Compliance escalation: {evidence.title}",
                        message=escalation.summary,
                        severity="escalation",
                        delivery_status="pending",
                        attempt_count=0,
                        max_attempts=5,
                        next_attempt_at=now,
                    ))
                    db.flush()

    db.commit()
    return {
        "as_of": run_date.isoformat(),
        "evidence_records_checked": len(rows),
        "notifications_queued": queued,
        "existing_notifications_skipped": skipped,
        "escalations_opened": escalated,
    }
