"""Guarded workflow actions, case timeline, chain verification, and policy registry."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.core import Application, User
from app.models.workflow import ApplicationEvent, PolicyVersion
from app.schemas.applications import ApplicationResponse
from app.schemas.workflow import EventChainVerification, EventResponse, PolicyResponse, TransitionRequest
from app.services.workflow import transition_application, verify_event_chain

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
