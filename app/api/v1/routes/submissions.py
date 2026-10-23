"""Scoped compliance undertaking submission lifecycle endpoints."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.auth.permissions import EVIDENCE_WRITE_ROLES
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.undertaking import ComplianceSubmission
from app.schemas.undertakings import ComplianceSubmissionCreate, ComplianceSubmissionResponse
from app.services.workflow import append_event

router = APIRouter()


def _visible_application(db: Session, user: User, application_id: UUID) -> Application:
    application = db.scalar(
        scoped_applications_statement(user).where(Application.id == application_id)
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def _validate_evidence(db: Session, application_id: UUID, evidence_ids: list[UUID]) -> None:
    if len(set(evidence_ids)) != len(evidence_ids):
        raise HTTPException(status_code=422, detail="Evidence identifiers must be unique")
    if not evidence_ids:
        raise HTTPException(status_code=422, detail="At least one evidence item is required")
    found = set(db.scalars(
        select(ApplicationEvidence.id).where(
            ApplicationEvidence.application_id == application_id,
            ApplicationEvidence.id.in_(evidence_ids),
        )
    ).all())
    if found != set(evidence_ids):
        raise HTTPException(status_code=422, detail="Evidence must belong to the selected application")


@router.get(
    "/applications/{application_id}/submissions",
    response_model=list[ComplianceSubmissionResponse],
    summary="List compliance submissions for a visible application",
)
def list_submissions(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ComplianceSubmission]:
    _visible_application(db, user, application_id)
    return list(db.scalars(
        select(ComplianceSubmission)
        .where(ComplianceSubmission.application_id == application_id)
        .order_by(ComplianceSubmission.created_at.desc(), ComplianceSubmission.version.desc())
    ).all())


@router.get(
    "/submissions",
    response_model=list[ComplianceSubmissionResponse],
    summary="List compliance submissions within the user's scope",
)
def list_scoped_submissions(
    status_filter: str | None = Query(default=None, alias="status", max_length=30),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ComplianceSubmission]:
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    statement = select(ComplianceSubmission).where(
        ComplianceSubmission.application_id.in_(select(visible_ids.c.id))
    )
    if status_filter:
        statement = statement.where(ComplianceSubmission.status == status_filter)
    return list(db.scalars(
        statement.order_by(ComplianceSubmission.created_at.desc()).limit(200)
    ).all())


@router.post(
    "/applications/{application_id}/submissions",
    response_model=ComplianceSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and submit a compliance undertaking",
)
def create_submission(
    application_id: UUID,
    payload: ComplianceSubmissionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ComplianceSubmission:
    if user.role not in EVIDENCE_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot submit compliance undertakings")
    application = _visible_application(db, user, application_id)
    _validate_evidence(db, application.id, payload.evidence_ids)

    latest_version = db.scalar(
        select(ComplianceSubmission.version)
        .where(
            ComplianceSubmission.application_id == application.id,
            ComplianceSubmission.submission_type == payload.submission_type,
        )
        .order_by(ComplianceSubmission.version.desc())
        .limit(1)
    ) or 0
    now = datetime.now(UTC)
    submission = ComplianceSubmission(
        application_id=application.id,
        submission_type=payload.submission_type,
        title=payload.title,
        declaration=payload.declaration,
        evidence_ids=[str(item) for item in payload.evidence_ids],
        status="submitted",
        version=latest_version + 1,
        submitted_by_user_id=user.id,
        submitted_at=now,
    )
    db.add(submission)
    db.flush()
    append_event(
        db,
        application_id=application.id,
        event_type="compliance_submission_created",
        from_status=application.status,
        to_status=application.status,
        actor_user_id=user.id,
        metadata={
            "submission_id": str(submission.id),
            "submission_type": submission.submission_type,
            "version": submission.version,
            "evidence_ids": submission.evidence_ids,
            "status": submission.status,
        },
    )
    db.commit()
    db.refresh(submission)
    return submission
