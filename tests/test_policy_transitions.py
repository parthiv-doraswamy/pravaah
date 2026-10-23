"""Policy-driven transitions and human-decision guard tests."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.routes.workflow import activate_policy_version, create_policy_version
from app.models.core import Application, Institution, User
from app.models.evidence import ApplicationEvidence
from app.models.workflow import ApplicationEvent, PolicyVersion
from app.schemas.workflow import PolicyCreate
from app.services.workflow import transition_application, verify_event_chain


def _setup(db, suffix: str):
    institution = Institution(
        name=f"Policy Workflow Institution {suffix}",
        code=f"PWF-{suffix}",
        region_code="PWF-REGION",
    )
    db.add(institution)
    db.flush()
    users = {}
    for role in ("institution_user", "scrutiny_officer", "competent_authority", "policy_admin", "bureau_officer"):
        user = User(
            email=f"pwf-{suffix}-{role}@example.test",
            full_name=f"Policy Workflow {role}",
            role=role,
            institution_id=institution.id,
        )
        db.add(user)
        users[role] = user
    application = Application(
        application_number=f"PVH-PWF-{suffix}",
        title="Policy workflow test",
        summary="Test summary",
        status="draft",
        institution_id=institution.id,
    )
    db.add(application)
    db.commit()
    for user in users.values():
        db.refresh(user)
    db.refresh(application)
    return users, application


def _policy_payload() -> PolicyCreate:
    return PolicyCreate(
        policy_key="application_workflow",
        version=1,
        title="Synthetic application workflow",
        description="Test-only configurable workflow; not official AICTE policy.",
        effective_from=datetime.now(UTC) - timedelta(days=1),
        source_label="Synthetic CI test policy",
        rules={
            "transitions": [
                {"from_status": "draft", "to_status": "submitted", "allowed_roles": ["institution_user"]},
                {"from_status": "submitted", "to_status": "under_scrutiny", "allowed_roles": ["scrutiny_officer"]},
                {"from_status": "under_scrutiny", "to_status": "returned", "allowed_roles": ["scrutiny_officer"]},
                {"from_status": "returned", "to_status": "submitted", "allowed_roles": ["institution_user"]},
                {
                    "from_status": "pending_authority_decision",
                    "to_status": "approved",
                    "allowed_roles": ["competent_authority"],
                    "requires_human_approval": True,
                },
            ],
            "prerequisites": [
                {
                    "status": "submitted",
                    "required_fields": ["title", "institution_id"],
                    "required_evidence_categories": ["identity_document"],
                }
            ],
        },
    )


def test_activated_policy_drives_returns_and_enforces_evidence_prerequisites(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        users, application = _setup(db, "001")
        policy = create_policy_version(_policy_payload(), db, users["policy_admin"])
        assert policy.is_active is False
        active = activate_policy_version(
            "application_workflow", 1, db, users["policy_admin"]
        )
        assert active.is_active is True

        with pytest.raises(HTTPException) as exc:
            transition_application(
                db, application=application, actor=users["institution_user"],
                target_status="submitted", expected_status="draft",
            )
        assert exc.value.status_code == 409
        assert application.status == "draft"

        db.add(ApplicationEvidence(
            application_id=application.id,
            title="Identity evidence",
            category="identity_document",
            created_by_user_id=users["institution_user"].id,
        ))
        db.commit()

        application = transition_application(
            db, application=application, actor=users["institution_user"],
            target_status="submitted", expected_status="draft",
        )
        application = transition_application(
            db, application=application, actor=users["scrutiny_officer"],
            target_status="under_scrutiny", expected_status="submitted",
        )
        application = transition_application(
            db, application=application, actor=users["scrutiny_officer"],
            target_status="returned", expected_status="under_scrutiny",
            reason="Please correct the submitted application",
        )
        assert application.status == "returned"

        events = list(db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application.id)
            .order_by(ApplicationEvent.sequence)
        ).all())
        assert verify_event_chain(events) == (True, None)
        assert events[1].event_metadata == {
            "policy_key": "application_workflow",
            "policy_version": 1,
            "policy_rules_schema_version": 1,
        }


def test_active_policy_denies_unconfigured_transition(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        users, application = _setup(db, "002")
        create_policy_version(_policy_payload(), db, users["policy_admin"])
        activate_policy_version("application_workflow", 1, db, users["policy_admin"])

        with pytest.raises(HTTPException) as exc:
            transition_application(
                db, application=application, actor=users["institution_user"],
                target_status="approved", expected_status="draft",
            )
        assert exc.value.status_code == 409
        db.refresh(application)
        assert application.status == "draft"
        assert db.scalar(select(ApplicationEvent).where(
            ApplicationEvent.application_id == application.id,
            ApplicationEvent.event_type == "status_transition",
        )) is None


def test_only_policy_admin_can_activate_policy(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        users, _ = _setup(db, "003")
        create_policy_version(_policy_payload(), db, users["policy_admin"])
        with pytest.raises(HTTPException) as exc:
            activate_policy_version("application_workflow", 1, db, users["scrutiny_officer"])
        assert exc.value.status_code == 403
        policy = db.scalar(select(PolicyVersion).where(PolicyVersion.policy_key == "application_workflow"))
        assert policy is not None
        assert policy.is_active is False
