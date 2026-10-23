"""Tests for optional SMTP delivery, retry backoff, and attempt auditing."""

from datetime import UTC, datetime, timedelta

from app.models.core import Application, Institution, User
from app.models.notification import NotificationRecord
from app.models.notification_attempt import NotificationAttempt
from app.services.notification_delivery import process_due_notifications


def seed_notification(db_factory):
    with db_factory() as db:
        institution = Institution(name="Delivery Test College", code="DL-001", region_code="REGION-D")
        db.add(institution)
        db.flush()
        user = User(
            email="delivery-recipient@example.test", full_name="Delivery Recipient",
            role="institution_user", institution_id=institution.id,
        )
        case = Application(
            application_number="PVH-DL-001", title="Delivery test case",
            status="under_scrutiny", institution_id=institution.id,
        )
        db.add_all([user, case])
        db.flush()
        record = NotificationRecord(
            recipient_user_id=user.id, application_id=case.id, evidence_id=None,
            dedupe_key="delivery-test-001", notification_type="test", title="Test reminder",
            message="This is a test reminder.", severity="info", delivery_status="pending",
            attempt_count=0, max_attempts=3, next_attempt_at=None,
        )
        db.add(record)
        db.commit()
        return record.id


def test_delivery_retries_with_backoff_and_records_attempts(api_client_and_sessions):
    _, db_factory = api_client_and_sessions
    notification_id = seed_notification(db_factory)
    now = datetime(2026, 10, 22, 10, 0, tzinfo=UTC)
    calls = {"count": 0}

    def flaky_transport(recipient, subject, body):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("temporary SMTP outage")

    with db_factory() as db:
        first = process_due_notifications(db, transport=flaky_transport, now=now, enabled=True)
    assert first["attempted"] == 1
    assert first["sent"] == 0

    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        assert record.attempt_count == 1
        assert record.delivery_status == "pending"
        assert record.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(minutes=5)
        attempt = db.query(NotificationAttempt).filter_by(notification_id=notification_id).one()
        assert attempt.outcome == "retry_scheduled"
        assert attempt.error_message == "Email delivery failed (OSError); provider details redacted."
        assert "temporary SMTP outage" not in attempt.error_message

    with db_factory() as db:
        second = process_due_notifications(
            db, transport=flaky_transport, now=now + timedelta(minutes=6), enabled=True
        )
    assert second["sent"] == 1
    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        assert record.delivery_status == "sent"
        assert record.attempt_count == 2
        assert record.sent_at.replace(tzinfo=UTC) == now + timedelta(minutes=6)
        assert db.query(NotificationAttempt).filter_by(notification_id=notification_id).count() == 2


def test_delivery_is_deferred_when_smtp_is_not_configured(api_client_and_sessions):
    _, db_factory = api_client_and_sessions
    notification_id = seed_notification(db_factory)
    with db_factory() as db:
        result = process_due_notifications(db, enabled=False)
    assert result["attempted"] == 0
    assert result["deferred"] == 1
    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        assert record.delivery_status == "pending"
        assert record.attempt_count == 0
        assert db.query(NotificationAttempt).count() == 0


def test_delivery_stops_after_configured_attempt_limit(api_client_and_sessions):
    _, db_factory = api_client_and_sessions
    notification_id = seed_notification(db_factory)
    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        record.max_attempts = 1
        db.commit()

    def failing_transport(recipient, subject, body):
        raise OSError("permanent SMTP rejection")

    with db_factory() as db:
        result = process_due_notifications(
            db,
            transport=failing_transport,
            now=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
            enabled=True,
        )
    assert result["failed"] == 1
    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        assert record.delivery_status == "failed"
        assert record.attempt_count == 1
        attempt = db.query(NotificationAttempt).filter_by(notification_id=notification_id).one()
        assert attempt.outcome == "failed"
        assert attempt.next_attempt_at is None


def test_delivery_skips_and_closes_notifications_for_inactive_recipients(api_client_and_sessions):
    _, db_factory = api_client_and_sessions
    notification_id = seed_notification(db_factory)
    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        recipient = db.get(User, record.recipient_user_id)
        recipient.is_active = False
        db.commit()

    transport_calls = {"count": 0}

    def should_not_send(recipient, subject, body):
        transport_calls["count"] += 1
        raise AssertionError("inactive recipients must not receive email")

    with db_factory() as db:
        result = process_due_notifications(
            db,
            transport=should_not_send,
            now=datetime(2026, 10, 22, 10, 0, tzinfo=UTC),
            enabled=True,
        )

    assert result["processed"] == 1
    assert result["attempted"] == 0
    assert result["sent"] == 0
    assert result["failed"] == 1
    assert result["skipped_inactive_recipients"] == 1
    assert transport_calls["count"] == 0
    with db_factory() as db:
        record = db.get(NotificationRecord, notification_id)
        assert record.delivery_status == "failed"
        assert record.attempt_count == 0
        assert record.next_attempt_at is None
        assert "account is inactive" in record.last_error
        assert db.query(NotificationAttempt).filter_by(notification_id=notification_id).count() == 0

