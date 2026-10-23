"""Persistent in-app notifications and idempotent expiry-alert queueing."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user, require_roles
from app.auth.permissions import NOTIFICATION_QUEUE_ROLES
from app.core.clock import utc_now, utc_today
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.notification import NotificationRecord
from app.schemas.notifications import NotificationOperationsItem, NotificationOperationsSummary, NotificationQueueResult, NotificationResponse
from app.services.notification_jobs import expiry_severity
from app.services.workflow import append_event

router = APIRouter()


@router.get("", response_model=list[NotificationResponse], summary="List the signed-in user's notifications")
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[NotificationRecord]:
    limit = min(max(limit, 1), 100)
    statement = select(NotificationRecord).where(NotificationRecord.recipient_user_id == user.id)
    if unread_only:
        statement = statement.where(NotificationRecord.read_at.is_(None))
    return list(db.scalars(statement.order_by(NotificationRecord.created_at.desc()).limit(limit)).all())


@router.post("/{notification_id}/read", response_model=NotificationResponse, summary="Mark a notification as read")
def mark_notification_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationRecord:
    notification = db.scalar(select(NotificationRecord).where(
        NotificationRecord.id == notification_id,
        NotificationRecord.recipient_user_id == user.id,
    ))
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.read_at is None:
        notification.read_at = utc_now()
        db.commit()
        db.refresh(notification)
    return notification


@router.post(
    "/{notification_id}/retry",
    response_model=NotificationResponse,
    summary="Retry a failed notification delivery",
)
def retry_notification_delivery(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationRecord:
    """Requeue the signed-in user's failed notification without erasing attempt history."""
    notification = db.scalar(
        select(NotificationRecord)
        .where(
            NotificationRecord.id == notification_id,
            NotificationRecord.recipient_user_id == user.id,
        )
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.delivery_status != "failed":
        raise HTTPException(status_code=409, detail="Only failed notifications can be retried")
    if notification.attempt_count >= 10:
        raise HTTPException(status_code=409, detail="Notification reached the manual retry safety limit")

    now = utc_now()
    previous_attempt_limit = notification.max_attempts
    if notification.attempt_count >= notification.max_attempts:
        notification.max_attempts = min(notification.max_attempts + 1, 10)
    notification.delivery_status = "pending"
    notification.next_attempt_at = now
    notification.last_error = None
    notification.updated_at = now
    application = db.get(Application, notification.application_id)
    append_event(
        db,
        application_id=notification.application_id,
        event_type="notification_delivery_retry_requested",
        from_status=application.status if application else None,
        to_status=application.status if application else None,
        actor_user_id=user.id,
        metadata={
            "notification_id": str(notification.id),
            "attempt_count": notification.attempt_count,
            "previous_max_attempts": previous_attempt_limit,
            "max_attempts": notification.max_attempts,
            "source": "recipient_recovery",
        },
    )
    db.commit()
    db.refresh(notification)
    return notification




@router.get(
    "/operations",
    response_model=NotificationOperationsSummary,
    summary="Get scoped notification delivery operations",
)
def notification_operations(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTIFICATION_QUEUE_ROLES)),
) -> NotificationOperationsSummary:
    """Return delivery health and recent records across applications visible to an operations role."""
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).order_by(None).subquery()
    visible_app_ids = select(visible_ids.c.id)
    rows = db.execute(
        select(NotificationRecord, Application, User)
        .join(Application, Application.id == NotificationRecord.application_id)
        .join(User, User.id == NotificationRecord.recipient_user_id)
        .where(Application.id.in_(visible_app_ids))
        .order_by(NotificationRecord.created_at.desc())
    ).all()
    by_status: dict[str, int] = {}
    for record, _, _ in rows:
        by_status[record.delivery_status] = by_status.get(record.delivery_status, 0) + 1
    items = [
        NotificationOperationsItem(
            id=record.id,
            application_id=application.id,
            application_number=application.application_number,
            application_title=application.title,
            recipient_name=recipient.full_name,
            recipient_role=recipient.role,
            notification_type=record.notification_type,
            title=record.title,
            message=record.message,
            severity=record.severity,
            delivery_status=record.delivery_status,
            attempt_count=record.attempt_count,
            max_attempts=record.max_attempts,
            next_attempt_at=record.next_attempt_at,
            last_error=record.last_error,
            created_at=record.created_at,
            updated_at=record.updated_at,
            read_at=record.read_at,
            sent_at=record.sent_at,
        )
        for record, application, recipient in rows[:100]
    ]
    failed = by_status.get("failed", 0)
    retry_ready = sum(1 for record, _, _ in rows if record.delivery_status == "failed" and record.attempt_count < 10)
    return NotificationOperationsSummary(
        as_of=utc_now(), total=len(rows), by_status=by_status,
        failed=failed, retry_ready=retry_ready, exhausted=failed - retry_ready, items=items,
    )


@router.post(
    "/operations/{notification_id}/retry",
    response_model=NotificationResponse,
    summary="Retry a failed delivery within the caller's operational scope",
)
def retry_notification_for_operations(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTIFICATION_QUEUE_ROLES)),
) -> NotificationRecord:
    """Retry a failed record only when its application is visible to this operations user."""
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).order_by(None).subquery()
    notification = db.scalar(
        select(NotificationRecord)
        .where(NotificationRecord.id == notification_id, NotificationRecord.application_id.in_(select(visible_ids.c.id)))
        .with_for_update()
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.delivery_status != "failed":
        raise HTTPException(status_code=409, detail="Only failed notifications can be retried")
    if notification.attempt_count >= 10:
        raise HTTPException(status_code=409, detail="Notification reached the manual retry safety limit")
    now = utc_now()
    previous_attempt_limit = notification.max_attempts
    if notification.attempt_count >= notification.max_attempts:
        notification.max_attempts = min(notification.max_attempts + 1, 10)
    notification.delivery_status = "pending"
    notification.next_attempt_at = now
    notification.last_error = None
    notification.updated_at = now
    application = db.get(Application, notification.application_id)
    append_event(
        db, application_id=notification.application_id,
        event_type="notification_delivery_retry_requested",
        from_status=application.status if application else None,
        to_status=application.status if application else None,
        actor_user_id=user.id,
        metadata={
            "notification_id": str(notification.id), "attempt_count": notification.attempt_count,
            "previous_max_attempts": previous_attempt_limit, "max_attempts": notification.max_attempts,
            "source": "operations_console",
        },
    )
    db.commit()
    db.refresh(notification)
    return notification


@router.post(
    "/queue-expiry",
    response_model=NotificationQueueResult,
    summary="Queue idempotent in-app notifications for expiry alerts",
)
def queue_expiry_notifications(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*NOTIFICATION_QUEUE_ROLES)),
) -> NotificationQueueResult:
    """Create in-app records for visible expiring evidence; does not send email/SMS."""
    now = utc_now()
    today = utc_today(now)
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    rows = db.execute(
        select(ApplicationEvidence, Application, User)
        .join(Application, Application.id == ApplicationEvidence.application_id)
        .join(User, User.institution_id == Application.institution_id)
        .where(
            Application.id.in_(select(visible_ids.c.id)),
            User.role == "institution_user",
            User.is_active.is_(True),
            ApplicationEvidence.expires_on.is_not(None),
        )
        .order_by(ApplicationEvidence.expires_on.asc())
    ).all()

    created = 0
    skipped = 0
    recipient_ids: set[UUID] = set()
    audited_evidence: set[UUID] = set()
    for evidence, application, recipient in rows:
        classified = expiry_severity(evidence.expires_on, today)
        if classified is None:
            continue
        severity, days = classified
        recipient_ids.add(recipient.id)
        dedupe_key = f"expiry:{evidence.id}:{evidence.expires_on.isoformat()}:{severity}:{recipient.id}"
        exists = db.scalar(select(NotificationRecord.id).where(NotificationRecord.dedupe_key == dedupe_key))
        if exists is not None:
            skipped += 1
            continue

        day_text = "expired" if days < 0 else ("expires today" if days == 0 else f"expires in {days} day{'s' if days != 1 else ''}")
        record = NotificationRecord(
            recipient_user_id=recipient.id,
            application_id=application.id,
            evidence_id=evidence.id,
            dedupe_key=dedupe_key,
            notification_type="evidence_expiry",
            title=f"Evidence {day_text}: {evidence.title}",
            message=f"{application.application_number} — {application.title}. {evidence.title} {day_text}. Review the evidence record and arrange any required follow-up.",
            severity=severity,
            delivery_status="pending",
            attempt_count=0,
            max_attempts=5,
            next_attempt_at=None,
        )
        try:
            with db.begin_nested():
                db.add(record)
                db.flush()
        except IntegrityError:
            skipped += 1
            continue
        created += 1
        if evidence.id not in audited_evidence:
            append_event(
                db,
                application_id=application.id,
                event_type="expiry_notification_queued",
                from_status=application.status,
                to_status=application.status,
                actor_user_id=user.id,
                metadata={
                    "evidence_id": str(evidence.id),
                    "severity": severity,
                    "days_remaining": days,
                    "notification_date": today.isoformat(),
                },
            )
            audited_evidence.add(evidence.id)

    db.commit()
    return NotificationQueueResult(
        as_of=now,
        created=created,
        skipped_existing=skipped,
        recipient_count=len(recipient_ids),
        detail="In-app notification records queued. Email/SMS delivery and background retries are not configured.",
    )
