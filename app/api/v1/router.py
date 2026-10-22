"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1.routes.applications import router as applications_router
from app.api.v1.routes.compliance import router as compliance_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.evidence import router as evidence_router
from app.api.v1.routes.notifications import router as notifications_router
from app.api.v1.routes.workflow import router as workflow_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(applications_router, prefix="/applications", tags=["applications"])
api_router.include_router(workflow_router, prefix="/applications", tags=["workflow"])
api_router.include_router(evidence_router, prefix="/applications", tags=["evidence"])
api_router.include_router(compliance_router, prefix="/compliance", tags=["compliance"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
