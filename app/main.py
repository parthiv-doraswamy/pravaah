"""FastAPI entry point for PRAVAAH."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    description=(
        "Prototype for policy-driven approval workflows, compliance tracking, "
        "deadline monitoring, and auditable case history."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.get("/health/live", tags=["health"], summary="Liveness check")
def health_live() -> dict[str, str]:
    """Report that the API process is alive; does not imply dependencies are ready."""
    return {"status": "ok", "service": "pravaah-api"}


@app.get("/health/ready", tags=["health"], summary="Readiness check")
def health_ready() -> dict[str, str]:
    """Initial readiness endpoint; dependency checks will be added with the database phase."""
    return {"status": "ok", "service": "pravaah-api", "checks": "not_configured"}
