"""FastAPI entry point for PRAVAAH."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import get_engine

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


def database_is_ready() -> bool:
    """Return whether a simple query can run against the configured database."""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


@app.get("/health/live", tags=["health"], summary="Liveness check")
def health_live() -> dict[str, str]:
    """Report that the API process is alive, independent of dependency status."""
    return {"status": "ok", "service": "pravaah-api"}


@app.get("/health/ready", tags=["health"], summary="Readiness check")
def health_ready() -> dict[str, str]:
    """Report readiness only when the configured PostgreSQL connection is responsive."""
    if not database_is_ready():
        raise HTTPException(
            status_code=503,
            detail={
                "status": "error",
                "service": "pravaah-api",
                "checks": {"database": "unavailable"},
            },
        )
    return {
        "status": "ok",
        "service": "pravaah-api",
        "checks": {"database": "ok"},
    }
