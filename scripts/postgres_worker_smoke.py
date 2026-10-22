"""PostgreSQL-backed smoke test for expiry alerts, escalation, and audit integrity.

Run only after migrations and the synthetic development seed have completed.
"""

from datetime import UTC, date, datetime

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.core import Application
from app.models.evidence import ApplicationEvidence
from app.models.escalation import ComplianceEscalation
from app.models.notification import NotificationRecord
from app.models.workflow import ApplicationEvent
from app.services.notification_delivery import process_due_notifications
from app.services.notification_jobs import run_expiry_monitoring
from app.services.workflow import verify_event_chain

SMOKE_APPLICATION_NUMBER = "PVH-DEMO-1001"
SMOKE_EVIDENCE_TITLE = "CI PostgreSQL expiry smoke evidence"
SMOKE_EXPIRY_DATE = date(2000, 1, 1)


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        application = db.scalar(
            select(Application).where(
                Application.application_number == SMOKE_APPLICATION_NUMBER
            )
        )
        if application is None:
            raise RuntimeError("Synthetic demo application is missing; run scripts.seed_demo first")

        evidence = db.scalar(
            select(ApplicationEvidence).where(
                ApplicationEvidence.application_id == application.id,
                ApplicationEvidence.title == SMOKE_EVIDENCE_TITLE,
            )
        )
        if evidence is None:
            evidence = ApplicationEvidence(
                application_id=application.id,
                title=SMOKE_EVIDENCE_TITLE,
                category="ci_smoke_test",
                issued_on=date(1999, 1, 1),
                expires_on=SMOKE_EXPIRY_DATE,
                notes="Synthetic CI-only evidence; not a real institution record.",
            )
            db.add(evidence)
        else:
            evidence.expires_on = SMOKE_EXPIRY_DATE
        db.commit()
        evidence_id = evidence.id
        application_id = application.id

        first_scan = run_expiry_monitoring(db, today=datetime.now(UTC).date())
        second_scan = run_expiry_monitoring(db, today=datetime.now(UTC).date())
        if first_scan["notifications_queued"] < 2:
            raise AssertionError(f"Expected expiry and escalation notifications: {first_scan}")
        if second_scan["notifications_queued"] != 0:
            raise AssertionError(f"Worker scan was not idempotent: {second_scan}")

        evidence_notifications = list(
            db.scalars(
                select(NotificationRecord).where(
                    NotificationRecord.evidence_id == evidence_id,
                    NotificationRecord.notification_type.in_(
                        ["evidence_expiry", "compliance_escalation"]
                    ),
                )
            ).all()
        )
        if len(evidence_notifications) != 2:
            raise AssertionError(
                f"Expected two deduplicated notifications, found {len(evidence_notifications)}"
            )

        escalation = db.scalar(
            select(ComplianceEscalation).where(
                ComplianceEscalation.evidence_id == evidence_id,
                ComplianceEscalation.status == "open",
            )
        )
        if escalation is None:
            raise AssertionError("Expiry monitoring did not create an open escalation")

        events = list(
            db.scalars(
                select(ApplicationEvent)
                .where(ApplicationEvent.application_id == application_id)
                .order_by(ApplicationEvent.sequence)
            ).all()
        )
        valid, invalid_sequence = verify_event_chain(events)
        if not valid:
            raise AssertionError(f"Application audit chain invalid at sequence {invalid_sequence}")

        delivery = process_due_notifications(db, enabled=False)
        if delivery["attempted"] != 0:
            raise AssertionError("SMTP-disabled smoke test must not attempt email delivery")
        if delivery["deferred"] < 2:
            raise AssertionError(f"Expected queued notifications to remain pending: {delivery}")

        print(
            "PostgreSQL worker smoke test passed: expiry reminders deduplicated, "
            "escalation opened, audit chain valid, SMTP delivery safely deferred."
        )


if __name__ == "__main__":
    main()
