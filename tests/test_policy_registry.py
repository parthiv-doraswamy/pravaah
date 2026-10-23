"""Policy registry tests use synthetic demo configuration, not official AICTE rules."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.routes.workflow import create_policy_version
from app.models.core import Institution, User
from app.models.workflow import PolicyVersion
from app.schemas.workflow import PolicyCreate


def _user(db, suffix: str, role: str) -> User:
    institution = Institution(
        name=f"Policy Test Institution {suffix}", code=f"POL-{suffix}", region_code="POLICY-REGION"
    )
    db.add(institution)
    db.flush()
    user = User(
        email=f"policy-{suffix}@example.test", full_name="Policy Test User",
        role=role, institution_id=institution.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _payload(version: int = 1) -> PolicyCreate:
    return PolicyCreate(
        policy_key="synthetic_review_route",
        version=version,
        title="Synthetic review route",
        description="Test-only configurable route and prerequisites",
        effective_from=datetime.now(UTC) + timedelta(days=1),
        source_label="Synthetic CI test policy",
        rules={
            "transitions": [{
                "from_status": "draft",
                "to_status": "submitted",
                "allowed_roles": ["institution_user"],
            }],
            "prerequisites": [{
                "status": "submitted",
                "required_fields": ["title", "institution_id"],
                "required_evidence_categories": ["identity_document"],
            }],
        },
    )


def test_policy_admin_can_create_inactive_version_with_routes_and_prerequisites(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user = _user(db, "001", "policy_admin")
        policy = create_policy_version(_payload(), db, user)
        assert policy.policy_key == "synthetic_review_route"
        assert policy.version == 1
        assert policy.rules_schema_version == 1
        assert policy.is_active is False
        assert policy.rules["transitions"][0]["to_status"] == "submitted"
        assert policy.rules["prerequisites"][0]["required_evidence_categories"] == ["identity_document"]


def test_non_admin_cannot_create_policy_version(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user = _user(db, "002", "scrutiny_officer")
        with pytest.raises(HTTPException) as exc:
            create_policy_version(_payload(), db, user)
        assert exc.value.status_code == 403
        assert db.scalar(select(PolicyVersion)) is None


def test_invalid_policy_rules_are_rejected_before_persistence(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user = _user(db, "003", "policy_admin")
        payload = _payload()
        payload.rules["transitions"][0]["allowed_roles"] = ["unknown_role"]
        with pytest.raises(HTTPException) as exc:
            create_policy_version(payload, db, user)
        assert exc.value.status_code == 422
        assert db.scalar(select(PolicyVersion)) is None


def test_policy_versions_must_increase_and_existing_version_is_unchanged(api_client_and_sessions):
    _, session_factory = api_client_and_sessions
    with session_factory() as db:
        user = _user(db, "004", "system_admin")
        first = create_policy_version(_payload(1), db, user)
        with pytest.raises(HTTPException) as exc:
            create_policy_version(_payload(1), db, user)
        assert exc.value.status_code == 409
        versions = list(db.scalars(select(PolicyVersion)).all())
        assert len(versions) == 1
        assert versions[0].id == first.id


def test_policy_effective_time_must_include_timezone():
    data = _payload().model_dump()
    data["effective_from"] = datetime(2026, 10, 23)
    with pytest.raises(ValueError, match="must include a timezone"):
        PolicyCreate(**data)
