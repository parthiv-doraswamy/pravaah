"""Evidence metadata registration and expiry tracking for scoped applications."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.schemas.evidence import EvidenceCreate, EvidenceResponse
from app.services.workflow import append_event

router = APIRouter()
_EVIDENCE_WRITE_ROLES = {
    "institution_user", "scrutiny_officer", "regional_officer", "bureau_officer",
    "evc_coordinator", "competent_authority", "policy_admin", "system_admin",
}


def _visible_application(db: Session, user: User, application_id: UUID) -> Application:
    application = db.scalar(scoped_applications_statement(user).where(Application.id == application_id))
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.get("/{application_id}/evidence", response_model=list[EvidenceResponse], summary="List evidence metadata for a visible application")
def list_evidence(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ApplicationEvidence]:
    _visible_application(db, user, application_id)
    return list(db.scalars(
        select(ApplicationEvidence)
        .where(ApplicationEvidence.application_id == application_id)
        .order_by(ApplicationEvidence.expires_on.asc().nullslast(), ApplicationEvidence.created_at.desc())
    ).all())


@router.post(
    "/{application_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register evidence metadata",
)
def create_evidence(
    application_id: UUID,
    payload: EvidenceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationEvidence:
    if user.role not in _EVIDENCE_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot register evidence")
    application = _visible_application(db, user, application_id)
    if payload.issued_on and payload.expires_on and payload.expires_on < payload.issued_on:
        raise HTTPException(status_code=422, detail="Expiry date cannot be earlier than issue date")
    evidence = ApplicationEvidence(
        application_id=application.id,
        title=payload.title,
        category=payload.category,
        reference_number=payload.reference_number,
        issued_on=payload.issued_on,
        expires_on=payload.expires_on,
        policy_key=payload.policy_key,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(evidence)
    db.flush()
    append_event(
        db,
        application_id=application.id,
        event_type="evidence_registered",
        from_status=application.status,
        to_status=application.status,
        actor_user_id=user.id,
        metadata={
            "evidence_id": str(evidence.id),
            "title": evidence.title,
            "category": evidence.category,
            "policy_key": evidence.policy_key,
            "expires_on": evidence.expires_on.isoformat() if evidence.expires_on else None,
        },
    )
    db.commit()
    db.refresh(evidence)
    return evidence
