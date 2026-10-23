"""FastAPI entry point for PRAVAAH."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.session import get_engine

settings = get_settings()


def run_database_migrations() -> None:
    """Apply pending Alembic revisions using the configured database URL."""
    config_path = Path(__file__).resolve().parent.parent / "alembic.ini"
    command.upgrade(Config(str(config_path)), "head")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Ensure production schema is current before the API starts serving traffic."""
    if settings.app_env.lower() == "production":
        run_database_migrations()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Prototype for policy-driven approval workflows, compliance tracking, "
        "deadline monitoring, and auditable case history."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

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
def health_ready() -> dict[str, object]:
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
