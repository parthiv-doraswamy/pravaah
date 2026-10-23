"""Scoped compliance submission, review, and correction endpoints."""
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
from app.schemas.undertakings import ComplianceSubmissionCreate, ComplianceSubmissionResponse, ComplianceSubmissionReview
from app.services.workflow import append_event

router = APIRouter()
SUBMISSION_REVIEW_ROLES = frozenset({"scrutiny_officer", "regional_officer", "bureau_officer", "competent_authority", "policy_admin", "system_admin"})

def _visible_application(db: Session, user: User, application_id: UUID) -> Application:
    application = db.scalar(scoped_applications_statement(user).where(Application.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application

def _validate_evidence(db: Session, application_id: UUID, evidence_ids: list[UUID]) -> None:
    if len(set(evidence_ids)) != len(evidence_ids):
        raise HTTPException(status_code=422, detail="Evidence identifiers must be unique")
    if not evidence_ids:
        raise HTTPException(status_code=422, detail="At least one evidence item is required")
    found = set(db.scalars(select(ApplicationEvidence.id).where(ApplicationEvidence.application_id == application_id, ApplicationEvidence.id.in_(evidence_ids))).all())
    if found != set(evidence_ids):
        raise HTTPException(status_code=422, detail="Evidence must belong to the selected application")

def _record_event(db: Session, submission: ComplianceSubmission, application: Application, user: User, event_type: str, extra: dict | None = None) -> None:
    metadata = {"submission_id": str(submission.id), "submission_type": submission.submission_type, "version": submission.version, "status": submission.status}
    if extra:
        metadata.update(extra)
    append_event(db, application_id=application.id, event_type=event_type, from_status=application.status, to_status=application.status, actor_user_id=user.id, metadata=metadata)

@router.get("/applications/{application_id}/submissions", response_model=list[ComplianceSubmissionResponse], summary="List submissions for a visible application")
def list_submissions(application_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ComplianceSubmission]:
    _visible_application(db, user, application_id)
    return list(db.scalars(select(ComplianceSubmission).where(ComplianceSubmission.application_id == application_id).order_by(ComplianceSubmission.created_at.desc(), ComplianceSubmission.version.desc())).all())

@router.get("/submissions", response_model=list[ComplianceSubmissionResponse], summary="List submissions in the user's scope")
def list_scoped_submissions(status_filter: str | None = Query(default=None, alias="status", max_length=30), db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ComplianceSubmission]:
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    statement = select(ComplianceSubmission).where(ComplianceSubmission.application_id.in_(select(visible_ids.c.id)))
    if status_filter:
        statement = statement.where(ComplianceSubmission.status == status_filter)
    return list(db.scalars(statement.order_by(ComplianceSubmission.created_at.desc()).limit(200)).all())

@router.post("/applications/{application_id}/submissions", response_model=ComplianceSubmissionResponse, status_code=status.HTTP_201_CREATED, summary="Create a compliance undertaking")
def create_submission(application_id: UUID, payload: ComplianceSubmissionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ComplianceSubmission:
    if user.role not in EVIDENCE_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot submit compliance undertakings")
    application = _visible_application(db, user, application_id)
    _validate_evidence(db, application.id, payload.evidence_ids)
    db.scalar(select(Application.id).where(Application.id == application.id).with_for_update())
    latest = db.scalar(select(ComplianceSubmission.version).where(ComplianceSubmission.application_id == application.id, ComplianceSubmission.submission_type == payload.submission_type).order_by(ComplianceSubmission.version.desc()).limit(1)) or 0
    submission = ComplianceSubmission(application_id=application.id, submission_type=payload.submission_type, title=payload.title, declaration=payload.declaration, evidence_ids=[str(item) for item in payload.evidence_ids], status="submitted", version=latest + 1, submitted_by_user_id=user.id, submitted_at=datetime.now(UTC))
    db.add(submission)
    db.flush()
    _record_event(db, submission, application, user, "compliance_submission_created")
    db.commit()
    db.refresh(submission)
    return submission

@router.post("/submissions/{submission_id}/review", response_model=ComplianceSubmissionResponse, summary="Record a submission review decision")
def review_submission(submission_id: UUID, payload: ComplianceSubmissionReview, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ComplianceSubmission:
    if user.role not in SUBMISSION_REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot review compliance submissions")
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    submission = db.scalar(select(ComplianceSubmission).where(ComplianceSubmission.id == submission_id, ComplianceSubmission.application_id.in_(select(visible_ids.c.id))).with_for_update())
    if submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted records can be reviewed")
    if payload.decision in {"changes_requested", "rejected"} and not (payload.notes or "").strip():
        raise HTTPException(status_code=422, detail="Review notes are required for this decision")
    application = _visible_application(db, user, submission.application_id)
    submission.status = payload.decision
    submission.reviewed_by_user_id = user.id
    submission.reviewed_at = datetime.now(UTC)
    submission.review_notes = (payload.notes or "").strip() or None
    _record_event(db, submission, application, user, "compliance_submission_reviewed", {"decision": payload.decision, "review_notes": submission.review_notes})
    db.commit()
    db.refresh(submission)
    return submission

@router.post("/submissions/{submission_id}/resubmit", response_model=ComplianceSubmissionResponse, status_code=status.HTTP_201_CREATED, summary="Submit a corrected version")
def resubmit_submission(submission_id: UUID, payload: ComplianceSubmissionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ComplianceSubmission:
    if user.role != "institution_user":
        raise HTTPException(status_code=403, detail="Only institution users can submit corrections")
    original = db.scalar(select(ComplianceSubmission).where(ComplianceSubmission.id == submission_id).with_for_update())
    if original is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    application = _visible_application(db, user, original.application_id)
    if original.status != "changes_requested":
        raise HTTPException(status_code=409, detail="Only submissions awaiting corrections can be resubmitted")
    if payload.submission_type != original.submission_type:
        raise HTTPException(status_code=422, detail="A correction must keep the original submission type")
    _validate_evidence(db, application.id, payload.evidence_ids)
    db.scalar(select(Application.id).where(Application.id == application.id).with_for_update())
    latest = db.scalar(select(ComplianceSubmission.version).where(ComplianceSubmission.application_id == application.id, ComplianceSubmission.submission_type == original.submission_type).order_by(ComplianceSubmission.version.desc()).limit(1)) or original.version
    corrected = ComplianceSubmission(application_id=application.id, submission_type=original.submission_type, title=payload.title, declaration=payload.declaration, evidence_ids=[str(item) for item in payload.evidence_ids], status="submitted", version=latest + 1, submitted_by_user_id=user.id, submitted_at=datetime.now(UTC), supersedes_submission_id=original.id)
    db.add(corrected)
    db.flush()
    _record_event(db, corrected, application, user, "compliance_submission_resubmitted", {"supersedes_submission_id": str(original.id)})
    db.commit()
    db.refresh(corrected)
    return corrected
