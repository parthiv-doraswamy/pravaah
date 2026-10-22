"""Tests for guarded transitions and tamper-evident event history."""

from fastapi import HTTPException
from sqlalchemy import select

from app.models.core import Application, Institution, User
from app.models.workflow import ApplicationEvent
from app.services.workflow import append_event, transition_application, verify_event_chain


def _case(db, suffix: str, role: str = "institution_user", status: str = "draft"):
    institution = Institution(name=f"Workflow College {suffix}", code=f"WF-{suffix}", region_code="REGION-A")
    db.add(institution)
    db.flush()
    user = User(
        email=f"workflow-{suffix}@example.test", full_name="Workflow Test User",
        role=role, institution_id=institution.id,
    )
    application = Application(
        application_number=f"PVH-WF-{suffix}", title="Workflow test case",
        status=status, institution_id=institution.id,
    )
    db.add_all([user, application])
    db.commit()
    db.refresh(user)
    db.refresh(application)
    return user, application


def test_institution_submission_creates_verifiable_event(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user, application = _case(db, "001")
        result = transition_application(
            db, application=application, actor=user, target_status="submitted",
            expected_status="draft", reason="Ready for review",
        )
        events = list(db.scalars(
            select(ApplicationEvent).where(ApplicationEvent.application_id == result.id)
            .order_by(ApplicationEvent.sequence)
        ).all())
        assert result.status == "submitted"
        assert len(events) == 1
        assert events[0].from_status == "draft"
        assert events[0].to_status == "submitted"
        assert verify_event_chain(events) == (True, None)


def test_invalid_transition_is_rejected_without_mutation(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user, application = _case(db, "002")
        try:
            transition_application(
                db, application=application, actor=user, target_status="approved",
                expected_status="draft",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("A draft must not be approved directly")
        db.refresh(application)
        assert application.status == "draft"


def test_stale_expected_status_is_rejected(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user, application = _case(db, "003")
        try:
            transition_application(
                db, application=application, actor=user, target_status="submitted",
                expected_status="submitted",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("Stale expected status must be rejected")
        assert application.status == "draft"


def test_event_chain_detects_tampering(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user, application = _case(db, "004")
        append_event(
            db, application_id=application.id, event_type="created",
            from_status=None, to_status="draft", actor_user_id=user.id,
        )
        db.commit()
        events = list(db.scalars(
            select(ApplicationEvent).where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.sequence)
        ).all())
        assert verify_event_chain(events) == (True, None)
        events[0].reason = "altered after the fact"
        assert verify_event_chain(events) == (False, 1)
