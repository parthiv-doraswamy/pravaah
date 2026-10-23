"""Role-controlled EVC visit scheduling and history."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.routes.applications import scoped_applications_statement
from app.auth.dependencies import get_current_user, require_roles
from app.auth.permissions import EVC_SCHEDULER_ROLES
from app.db.session import get_db
from app.models.core import Application, User
from app.models.evc_visit import EVCVisit
from app.models.evidence import ApplicationEvidence
from app.schemas.evc import EVCReportUpdate, EVCVisitCreate, EVCVisitResponse, EVCVisitStatusUpdate
from app.services.workflow import append_event

logger = logging.getLogger(__name__)
router = APIRouter()
_ALLOWED_APPLICATION_STATUSES = {
    "submitted", "under_scrutiny", "recommended_for_approval",
    "pending_authority_decision", "evc_pending", "evc_scheduled",
}


@router.get("/visits", response_model=list[EVCVisitResponse], summary="List EVC visits in the user's scope")
def list_visits(
    application_id: UUID | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[EVCVisitResponse]:
    if status_filter is not None and status_filter not in {"scheduled", "completed", "cancelled"}:
        raise HTTPException(status_code=422, detail="Unsupported EVC visit status")

    try:
        # Keep authorization scope in the database query; never fetch visits and
        # filter them in Python, which could leak records across institution scopes.
        visible_applications = (
            scoped_applications_statement(user)
            .with_only_columns(Application.id)
            .order_by(None)
            .subquery()
        )
        statement = select(EVCVisit).where(
            EVCVisit.application_id.in_(select(visible_applications.c.id))
        )
        if application_id is not None:
            statement = statement.where(EVCVisit.application_id == application_id)
        if status_filter is not None:
            statement = statement.where(EVCVisit.status == status_filter)

        visits = db.scalars(
            statement.order_by(EVCVisit.scheduled_for.asc(), EVCVisit.id.asc()).limit(200)
        ).all()

        # Validate while the request context is active so any malformed legacy
        # JSON/UUID data is logged here rather than surfacing as an opaque
        # FastAPI response-serialization 500.
        return [EVCVisitResponse.model_validate(visit) for visit in visits]
    except HTTPException:
        raise
    except (SQLAlchemyError, ValueError, TypeError) as exc:
        logger.exception(
            "EVC visit list failed (user_id=%s, role=%s, application_id=%s, status_filter=%s)",
            getattr(user, "id", None),
            getattr(user, "role", None),
            application_id,
            status_filter,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to load EVC visits. The server recorded diagnostic details.",
        ) from exc


@router.post(
    "/visits",
    response_model=EVCVisitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an EVC visit",
)
def schedule_visit(
    payload: EVCVisitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EVC_SCHEDULER_ROLES)),
) -> EVCVisit:
    application = db.scalar(
        scoped_applications_statement(user).where(Application.id == payload.application_id)
    )
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if application.status not in _ALLOWED_APPLICATION_STATUSES:
        raise HTTPException(
            status_code=409,
            detail="EVC visits can only be scheduled for applications in an active review stage",
        )
    if payload.scheduled_for.astimezone(UTC) <= datetime.now(UTC):
        raise HTTPException(status_code=422, detail="scheduled_for must be in the future")
    if payload.mode == "onsite" and not (payload.location and payload.location.strip()):
        raise HTTPException(status_code=422, detail="An onsite visit requires a location")
    visit = EVCVisit(
        application_id=application.id,
        scheduled_for=payload.scheduled_for,
        mode=payload.mode,
        location=payload.location.strip() if payload.location else None,
        notes=payload.notes.strip() if payload.notes else None,
        status="scheduled",
        created_by_user_id=user.id,
    )
    db.add(visit)
    db.flush()
    append_event(
        db,
        application_id=application.id,
        event_type="evc_visit_scheduled",
        from_status=application.status,
        to_status=application.status,
        actor_user_id=user.id,
        reason="EVC visit scheduled",
        metadata={
            "visit_id": str(visit.id),
            "scheduled_for": visit.scheduled_for.isoformat(),
            "mode": visit.mode,
            "location": visit.location,
        },
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.post(
    "/visits/{visit_id}/status",
    response_model=EVCVisitResponse,
    summary="Complete or cancel a scheduled EVC visit",
)
def update_visit_status(
    visit_id: UUID,
    payload: EVCVisitStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EVC_SCHEDULER_ROLES)),
) -> EVCVisit:
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    visit = db.scalar(
        select(EVCVisit)
        .where(
            EVCVisit.id == visit_id,
            EVCVisit.application_id.in_(select(visible_ids.c.id)),
        )
        .with_for_update()
    )
    if visit is None:
        raise HTTPException(status_code=404, detail="EVC visit not found")
    if visit.status != "scheduled":
        raise HTTPException(status_code=409, detail="Only scheduled visits can be completed or cancelled")
    previous_status = visit.status
    visit.status = payload.status
    append_event(
        db,
        application_id=visit.application_id,
        event_type="evc_visit_status_changed",
        from_status=previous_status,
        to_status=visit.status,
        actor_user_id=user.id,
        reason=f"EVC visit {visit.status}",
        metadata={"visit_id": str(visit.id)},
    )
    db.commit()
    db.refresh(visit)
    return visit


@router.put(
    "/visits/{visit_id}/report",
    response_model=EVCVisitResponse,
    summary="Save or submit a structured EVC visit report",
)
def save_visit_report(
    visit_id: UUID,
    payload: EVCReportUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EVC_SCHEDULER_ROLES)),
) -> EVCVisit:
    visible_ids = scoped_applications_statement(user).with_only_columns(Application.id).subquery()
    visit = db.scalar(
        select(EVCVisit)
        .where(
            EVCVisit.id == visit_id,
            EVCVisit.application_id.in_(select(visible_ids.c.id)),
        )
        .with_for_update()
    )
    if visit is None:
        raise HTTPException(status_code=404, detail="EVC visit not found")
    if visit.status != "completed":
        raise HTTPException(status_code=409, detail="A report can only be recorded after the visit is completed")
    if visit.report_status == "submitted":
        raise HTTPException(status_code=409, detail="Submitted EVC reports are immutable")
    unique_evidence_ids = set(payload.evidence_ids)
    if len(unique_evidence_ids) != len(payload.evidence_ids):
        raise HTTPException(status_code=422, detail="Evidence links must not contain duplicates")
    if unique_evidence_ids:
        matching_evidence = db.scalars(
            select(ApplicationEvidence.id).where(
                ApplicationEvidence.application_id == visit.application_id,
                ApplicationEvidence.id.in_(unique_evidence_ids),
            )
        ).all()
        if set(matching_evidence) != unique_evidence_ids:
            raise HTTPException(
                status_code=422,
                detail="Every linked evidence item must belong to the same application as this visit",
            )
    visit.checklist = [item.model_dump() for item in payload.checklist]
    visit.linked_evidence_ids = [str(item) for item in payload.evidence_ids]
    visit.outcome_summary = payload.outcome_summary.strip()
    visit.observations = payload.observations.strip() if payload.observations else None
    previous_report_status = visit.report_status
    if payload.submit:
        visit.report_status = "submitted"
        visit.report_submitted_at = datetime.now(UTC)
    else:
        visit.report_status = "draft"
    db.flush()
    append_event(
        db,
        application_id=visit.application_id,
        event_type="evc_report_submitted" if payload.submit else "evc_report_saved",
        from_status=previous_report_status,
        to_status=visit.report_status,
        actor_user_id=user.id,
        reason="EVC outcome report submitted" if payload.submit else "EVC outcome report draft saved",
        metadata={
            "visit_id": str(visit.id),
            "report_status": visit.report_status,
            "checklist_items": len(visit.checklist or []),
            "linked_evidence_ids": visit.linked_evidence_ids or [],
            "needs_attention": sum(1 for item in visit.checklist or [] if item.get("result") == "needs_attention"),
        },
    )
    db.commit()
    db.refresh(visit)
    return visit
