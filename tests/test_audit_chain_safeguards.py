"""Regression tests for audit-chain scope and integrity invariants."""

from sqlalchemy import select

from app.models.core import Application, Institution, User
from app.models.workflow import ApplicationEvent
from app.services.workflow import append_event, verify_event_chain


def test_event_chain_rejects_events_mixed_from_different_applications(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        institution = Institution(
            name="Audit Chain Test Institution", code="AUDIT-CHAIN-01", region_code="AUDIT-REGION"
        )
        db.add(institution)
        db.flush()
        user = User(
            email="audit-chain-test@example.test",
            full_name="Audit Chain Test User",
            role="system_admin",
            institution_id=institution.id,
        )
        first = Application(
            application_number="PVH-AUDIT-CHAIN-01", title="First synthetic case",
            status="draft", institution_id=institution.id,
        )
        second = Application(
            application_number="PVH-AUDIT-CHAIN-02", title="Second synthetic case",
            status="draft", institution_id=institution.id,
        )
        db.add_all([user, first, second])
        db.flush()
        append_event(
            db, application_id=first.id, event_type="first_case_event",
            from_status=None, to_status="draft", actor_user_id=user.id,
        )
        append_event(
            db, application_id=second.id, event_type="second_case_event",
            from_status=None, to_status="draft", actor_user_id=user.id,
        )
        db.commit()
        events = list(db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id.in_([first.id, second.id]))
            .order_by(ApplicationEvent.application_id, ApplicationEvent.sequence)
        ).all())

        assert len(events) == 2
        assert verify_event_chain(events) == (False, events[1].sequence)
