"""Versioned API router."""

from fastapi import APIRouter

from app.api.v1.routes.applications import router as applications_router
from app.api.v1.routes.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])
api_router.include_router(applications_router, prefix="/applications", tags=["applications"])
