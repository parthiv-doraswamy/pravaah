"""Guarded workflow actions, case timeline, chain verification, and policy registry."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.core import Application, User
from app.models.workflow import ApplicationEvent, PolicyVersion
from app.schemas.applications import ApplicationResponse
from app.schemas.policy_rules import validate_policy_rules
from app.schemas.workflow import (
    EventChainVerification,
    EventResponse,
    PolicyCreate,
    PolicyResponse,
    TransitionRequest,
)
from app.services.workflow import WORKFLOW_POLICY_KEY, transition_application, verify_event_chain

router = APIRouter()


@router.post("/{application_id}/transitions", response_model=ApplicationResponse, summary="Perform a guarded status transition")
def transition_case(
    application_id: UUID,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Application:
    application = db.scalar(scoped_applications_statement(user).where(Application.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return transition_application(
        db, application=application, actor=user, target_status=payload.target_status,
        expected_status=payload.expected_status, reason=payload.reason,
    )


@router.get("/{application_id}/events", response_model=list[EventResponse], summary="Read the application event timeline")
def list_case_events(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApplicationEvent]:
    application = db.scalar(scoped_applications_statement(user).where(Application.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return list(db.scalars(
        select(ApplicationEvent).where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.sequence)
    ).all())


@router.get("/{application_id}/events/verify", response_model=EventChainVerification, summary="Verify the event hash chain")
def verify_case_events(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EventChainVerification:
    application = db.scalar(scoped_applications_statement(user).where(Application.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    events = list(db.scalars(
        select(ApplicationEvent).where(ApplicationEvent.application_id == application_id)
        .order_by(ApplicationEvent.sequence)
    ).all())
    valid, invalid_sequence = verify_event_chain(events)
    return EventChainVerification(
        application_id=application_id, valid=valid, event_count=len(events),
        first_invalid_sequence=invalid_sequence,
    )


@router.get("/policies/registry", response_model=list[PolicyResponse], summary="List published demo policy versions")
def list_policy_versions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PolicyVersion]:
    del user  # Authentication is required; policy visibility is read-only for signed-in roles.
    return list(db.scalars(
        select(PolicyVersion).order_by(PolicyVersion.policy_key, PolicyVersion.version.desc())
    ).all())


@router.post(
    "/policies/registry",
    response_model=PolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a validated, inactive policy version",
)
def create_policy_version(
    payload: PolicyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PolicyVersion:
    """Store a validated immutable version; activation is a separate reviewed action."""
    if user.role not in {"policy_admin", "system_admin"}:
        raise HTTPException(status_code=403, detail="Your role cannot create policy versions")
    try:
        validate_policy_rules(payload.rules_schema_version, payload.rules)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid policy rules: {exc}") from exc

    latest_version = db.scalar(
        select(func.max(PolicyVersion.version)).where(PolicyVersion.policy_key == payload.policy_key)
    )
    if latest_version is not None and payload.version <= latest_version:
        raise HTTPException(
            status_code=409,
            detail=f"Policy version must be greater than the latest version ({latest_version})",
        )

    policy = PolicyVersion(
        policy_key=payload.policy_key,
        version=payload.version,
        title=payload.title,
        description=payload.description,
        effective_from=payload.effective_from.astimezone(UTC),
        rules=payload.rules,
        rules_schema_version=payload.rules_schema_version,
        source_label=payload.source_label,
        is_active=False,
    )
    db.add(policy)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This policy version already exists") from exc
    db.refresh(policy)
    return policy


@router.post(
    "/policies/registry/{policy_key}/{version}/activate",
    response_model=PolicyResponse,
    summary="Activate a reviewed application workflow policy version",
)
def activate_policy_version(
    policy_key: str,
    version: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PolicyVersion:
    """Activate only the dedicated workflow policy; activation is an explicit admin action."""
    if user.role not in {"policy_admin", "system_admin"}:
        raise HTTPException(status_code=403, detail="Your role cannot activate policy versions")
    if policy_key != WORKFLOW_POLICY_KEY:
        raise HTTPException(
            status_code=422,
            detail=f"Runtime transition enforcement currently supports only '{WORKFLOW_POLICY_KEY}'",
        )
    policy = db.scalar(
        select(PolicyVersion).where(
            PolicyVersion.policy_key == policy_key,
            PolicyVersion.version == version,
        ).with_for_update()
    )
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy version not found")
    effective_from = policy.effective_from
    if effective_from.tzinfo is None:
        effective_from = effective_from.replace(tzinfo=UTC)
    if effective_from > datetime.now(UTC):
        raise HTTPException(status_code=409, detail="Policy is not effective yet")
    try:
        validate_policy_rules(policy.rules_schema_version, policy.rules)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid policy rules: {exc}") from exc

    db.execute(
        update(PolicyVersion)
        .where(PolicyVersion.policy_key == policy_key)
        .values(is_active=False)
    )
    policy.is_active = True
    db.commit()
    db.refresh(policy)
    return policy
