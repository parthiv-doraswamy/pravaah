"""Evidence metadata registration and expiry tracking for scoped applications."""

import hashlib
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user
from app.auth.permissions import EVIDENCE_WRITE_ROLES
from app.core.config import get_settings
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evidence import ApplicationEvidence
from app.models.evidence_attachment import EvidenceAttachment
from app.schemas.evidence import EvidenceAttachmentResponse, EvidenceCreate, EvidenceResponse
from app.services.workflow import append_event

router = APIRouter()


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
    if user.role not in EVIDENCE_WRITE_ROLES:
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



_ALLOWED_UPLOADS = {
    ".pdf": ("application/pdf", lambda data: data.startswith(b"%PDF-")),
    ".png": ("image/png", lambda data: data.startswith(b"\x89PNG\r\n\x1a\n")),
    ".jpg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
    ".jpeg": ("image/jpeg", lambda data: data.startswith(b"\xff\xd8\xff")),
}


def _attachment_path(storage_key: str) -> Path:
    """Resolve a generated storage key under the configured private upload directory."""
    root = Path(get_settings().evidence_storage_dir).resolve()
    path = (root / storage_key[:2] / storage_key).resolve()
    if root not in path.parents:
        raise HTTPException(status_code=500, detail="Invalid attachment storage reference")
    return path


@router.get(
    "/{application_id}/evidence/{evidence_id}/attachments",
    response_model=list[EvidenceAttachmentResponse],
    summary="List files attached to a registered evidence record",
)
def list_evidence_attachments(
    application_id: UUID,
    evidence_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EvidenceAttachment]:
    _visible_application(db, user, application_id)
    evidence = db.scalar(select(ApplicationEvidence).where(
        ApplicationEvidence.id == evidence_id,
        ApplicationEvidence.application_id == application_id,
    ))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    return list(db.scalars(
        select(EvidenceAttachment)
        .where(EvidenceAttachment.evidence_id == evidence_id)
        .order_by(EvidenceAttachment.created_at.desc())
    ).all())


@router.post(
    "/{application_id}/evidence/{evidence_id}/attachments",
    response_model=EvidenceAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a validated evidence attachment",
)
async def upload_evidence_attachment(
    application_id: UUID,
    evidence_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> EvidenceAttachment:
    if user.role not in EVIDENCE_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot upload evidence files")
    application = _visible_application(db, user, application_id)
    if application.status in {"approved", "rejected"}:
        raise HTTPException(
            status_code=409,
            detail="Evidence attachments cannot be added after the application is finalized",
        )
    evidence = db.scalar(select(ApplicationEvidence).where(
        ApplicationEvidence.id == evidence_id,
        ApplicationEvidence.application_id == application_id,
    ))
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidence record not found")

    filename = Path(file.filename or "attachment").name
    suffix = Path(filename).suffix.lower()
    file_spec = _ALLOWED_UPLOADS.get(suffix)
    if file_spec is None:
        raise HTTPException(status_code=415, detail="Only PDF, PNG, and JPEG files are supported")

    settings = get_settings()
    if settings.evidence_max_upload_bytes < 1:
        raise HTTPException(status_code=500, detail="Evidence upload limit is misconfigured")
    contents = await file.read(settings.evidence_max_upload_bytes + 1)
    if len(contents) > settings.evidence_max_upload_bytes:
        raise HTTPException(status_code=413, detail="File exceeds the configured upload size limit")
    content_type, signature_check = file_spec
    if not signature_check(contents):
        raise HTTPException(status_code=415, detail="File extension does not match supported file content")
    if not filename or filename in {".", ".."}:
        raise HTTPException(status_code=422, detail="A valid filename is required")

    storage_key = f"{uuid4().hex}{suffix}"
    destination = _attachment_path(storage_key)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents)
        attachment = EvidenceAttachment(
            application_id=application_id,
            evidence_id=evidence_id,
            original_filename=filename[:255],
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(contents),
            sha256_hex=hashlib.sha256(contents).hexdigest(),
            uploaded_by_user_id=user.id,
        )
        db.add(attachment)
        db.flush()
        append_event(
            db,
            application_id=application_id,
            event_type="evidence_file_uploaded",
            from_status=evidence.category,
            to_status=evidence.category,
            actor_user_id=user.id,
            reason="Evidence attachment uploaded",
            metadata={
                "evidence_id": str(evidence_id),
                "attachment_id": str(attachment.id),
                "filename": attachment.original_filename,
                "size_bytes": attachment.size_bytes,
                "sha256": attachment.sha256_hex,
            },
        )
        db.commit()
        db.refresh(attachment)
    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise
    return attachment


@router.get(
    "/{application_id}/evidence/{evidence_id}/attachments/{attachment_id}/download",
    summary="Download a private evidence attachment",
)
def download_evidence_attachment(
    application_id: UUID,
    evidence_id: UUID,
    attachment_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> FileResponse:
    _visible_application(db, user, application_id)
    attachment = db.scalar(select(EvidenceAttachment).where(
        EvidenceAttachment.id == attachment_id,
        EvidenceAttachment.application_id == application_id,
        EvidenceAttachment.evidence_id == evidence_id,
    ))
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")
    path = _attachment_path(attachment.storage_key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Attachment file is unavailable")
    return FileResponse(
        path=path,
        media_type=attachment.content_type,
        filename=attachment.original_filename,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )
