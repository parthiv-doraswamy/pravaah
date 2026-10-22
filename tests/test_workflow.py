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



def test_full_application_lifecycle_enforces_roles_and_verifies_timeline(api_client_and_sessions):
    """Exercise the real HTTP workflow from draft through human approval."""
    from app.auth.security import hash_password

    client, session_factory = api_client_and_sessions
    password = "Lifecycle-Test-123!"
    with session_factory() as db:
        institution = Institution(
            name="Lifecycle Test College", code="WF-LIFECYCLE", region_code="REGION-A"
        )
        db.add(institution)
        db.flush()
        roles = ("institution_user", "scrutiny_officer", "bureau_officer", "competent_authority")
        users = {}
        for role in roles:
            user = User(
                email=f"lifecycle-{role}@example.test",
                full_name=f"Lifecycle {role}",
                role=role,
                password_hash=hash_password(password),
                institution_id=institution.id,
            )
            db.add(user)
            users[role] = user
        application = Application(
            application_number="PVH-WF-LIFECYCLE",
            title="Lifecycle integration test",
            status="draft",
            institution_id=institution.id,
        )
        db.add(application)
        db.commit()
        application_id = application.id
        emails = {role: user.email for role, user in users.items()}

    tokens = {}
    for role, email in emails.items():
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert login.status_code == 200
        tokens[role] = {"Authorization": f"Bearer {login.json()['access_token']}"}

    def transition(role: str, expected: str, target: str, status_code: int = 200):
        response = client.post(
            f"/api/v1/applications/{application_id}/transitions",
            headers=tokens[role],
            json={
                "expected_status": expected,
                "target_status": target,
                "reason": f"Integration test: {role}",
            },
        )
        assert response.status_code == status_code, response.text
        if status_code == 200:
            assert response.json()["status"] == target
        return response

    # An institution user cannot bypass scrutiny, even with a valid token.
    transition("institution_user", "draft", "approved", status_code=409)
    # Each valid transition must be made by the role assigned to that stage.
    transition("institution_user", "draft", "submitted")
    transition("bureau_officer", "submitted", "pending_authority_decision", status_code=409)

    # A rejected role bypass must not mutate status or append an audit event.
    unchanged = client.get(
        f"/api/v1/applications/{application_id}",
        headers=tokens["institution_user"],
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["status"] == "submitted"
    timeline_after_denial = client.get(
        f"/api/v1/applications/{application_id}/events",
        headers=tokens["institution_user"],
    )
    assert timeline_after_denial.status_code == 200
    assert len(timeline_after_denial.json()) == 1
    verified_after_denial = client.get(
        f"/api/v1/applications/{application_id}/events/verify",
        headers=tokens["institution_user"],
    )
    assert verified_after_denial.status_code == 200
    assert verified_after_denial.json()["valid"] is True

    transition("scrutiny_officer", "submitted", "under_scrutiny")
    transition("scrutiny_officer", "under_scrutiny", "clarification_requested")
    transition("institution_user", "clarification_requested", "submitted")
    transition("scrutiny_officer", "submitted", "under_scrutiny")
    transition("scrutiny_officer", "under_scrutiny", "recommended_for_approval")
    transition("bureau_officer", "recommended_for_approval", "pending_authority_decision")
    transition("competent_authority", "pending_authority_decision", "approved")

    timeline = client.get(
        f"/api/v1/applications/{application_id}/events",
        headers=tokens["competent_authority"],
    )
    assert timeline.status_code == 200
    assert len(timeline.json()) == 8
    assert [event["sequence"] for event in timeline.json()] == list(range(1, 9))

    verification = client.get(
        f"/api/v1/applications/{application_id}/events/verify",
        headers=tokens["competent_authority"],
    )
    assert verification.status_code == 200
    assert verification.json()["valid"] is True
    assert verification.json()["event_count"] == 8

    final_case = client.get(
        f"/api/v1/applications/{application_id}",
        headers=tokens["institution_user"],
    )
    assert final_case.status_code == 200
    assert final_case.json()["status"] == "approved"


def test_multiple_events_in_one_transaction_receive_distinct_sequences(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user, application = _case(db, "005")
        append_event(
            db,
            application_id=application.id,
            event_type="first_event",
            from_status="draft",
            to_status="draft",
            actor_user_id=user.id,
        )
        append_event(
            db,
            application_id=application.id,
            event_type="second_event",
            from_status="draft",
            to_status="draft",
            actor_user_id=user.id,
        )
        db.commit()

        events = list(
            db.scalars(
                select(ApplicationEvent)
                .where(ApplicationEvent.application_id == application.id)
                .order_by(ApplicationEvent.sequence)
            ).all()
        )
        assert [event.sequence for event in events] == [1, 2]
        assert [event.event_type for event in events] == ["first_event", "second_event"]
        assert verify_event_chain(events) == (True, None)


def test_transition_refreshes_stale_application_before_state_check(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as first_session:
        user, application = _case(first_session, "006")
        stale_application = first_session.get(Application, application.id)
        with session_factory() as second_session:
            concurrent_copy = second_session.get(Application, application.id)
            concurrent_copy.status = "submitted"
            second_session.commit()

        try:
            transition_application(
                first_session,
                application=stale_application,
                actor=user,
                target_status="submitted",
                expected_status="draft",
            )
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("A stale draft view must not overwrite a newer status")

        first_session.refresh(stale_application)
        assert stale_application.status == "submitted"

