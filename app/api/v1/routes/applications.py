"""Application registry endpoints with server-side role and institution scoping."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.session import get_db
from app.models.core import Application, Institution, User
from app.schemas.applications import ApplicationCreate, ApplicationPage, ApplicationResponse
from app.services.workflow import append_event

router = APIRouter()
_REVIEW_ROLES = {
    "scrutiny_officer",
    "regional_officer",
    "bureau_officer",
    "evc_coordinator",
    "competent_authority",
    "policy_admin",
    "auditor",
    "system_admin",
}


def scoped_applications_statement(user: User):
    """Build a query scoped to the authenticated user's permitted institution region."""
    statement = select(Application)
    if user.role == "institution_user":
        if user.institution_id is None:
            raise HTTPException(status_code=403, detail="No institution is assigned to this account")
        return statement.where(Application.institution_id == user.institution_id)
    if user.role == "regional_officer":
        if user.institution is None or not user.institution.region_code:
            raise HTTPException(status_code=403, detail="No region is assigned to this account")
        return statement.join(Institution).where(Institution.region_code == user.institution.region_code)
    if user.role in _REVIEW_ROLES:
        return statement
    raise HTTPException(status_code=403, detail="Your role cannot access the application registry")


@router.get("", response_model=ApplicationPage, summary="List applications visible to the current user")
def list_applications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    status_filter: str | None = Query(default=None, alias="status", max_length=60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ApplicationPage:
    statement = scoped_applications_statement(user)
    if q:
        term = f"%{q.strip()}%"
        statement = statement.where(
            (Application.application_number.ilike(term)) | (Application.title.ilike(term))
        )
    if status_filter:
        statement = statement.where(Application.status == status_filter)
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = db.scalar(count_statement) or 0
    items = db.scalars(
        statement.order_by(Application.updated_at.desc(), Application.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return ApplicationPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED, summary="Create a draft application")
def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Application:
    if user.role != "institution_user":
        raise HTTPException(status_code=403, detail="Only institution users can create applications")
    if user.institution_id is None:
        raise HTTPException(status_code=403, detail="No institution is assigned to this account")
    application = Application(
        application_number=f"PVH-{datetime.now(UTC):%Y%m%d}-{uuid4().hex[:8].upper()}",
        title=payload.title,
        summary=payload.summary,
        status="draft",
        institution_id=user.institution_id,
    )
    db.add(application)
    db.flush()
    append_event(
        db, application_id=application.id, event_type="application_created",
        from_status=None, to_status="draft", actor_user_id=user.id,
    )
    db.commit()
    db.refresh(application)
    return application


@router.get("/{application_id}", response_model=ApplicationResponse, summary="Get one visible application")
def get_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Application:
    statement = scoped_applications_statement(user).where(Application.id == application_id)
    application = db.scalar(statement)
    if application is None:
        # Do not reveal whether an out-of-scope application exists.
        raise HTTPException(status_code=404, detail="Application not found")
    return application
