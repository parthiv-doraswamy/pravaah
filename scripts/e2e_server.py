"""Start an isolated database-backed API for real browser integration tests.

This entry point is only for local/CI E2E. It accepts either the dedicated
SQLite test file or a local PostgreSQL database named pravaah_e2e. It
refuses arbitrary database URLs to reduce the risk of touching real data.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import uvicorn
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  Ensure every mapped model is registered before create_all.
from scripts.seed_demo import main as seed_demo


def _is_allowed_test_database(database_url: str) -> tuple[bool, str]:
    """Allow only the known disposable SQLite file or local E2E PostgreSQL database."""
    if database_url == "sqlite:///./var/pravaah-e2e.sqlite3":
        return True, "sqlite"

    parsed = urlsplit(database_url)
    is_local_postgres = (
        parsed.scheme == "postgresql+psycopg"
        and parsed.hostname in {"127.0.0.1", "localhost"}
        and parsed.port == 5432
        and unquote(parsed.username or "") == "pravaah"
        and parsed.path == "/pravaah_e2e"
        and not parsed.query
    )
    if is_local_postgres:
        return True, "postgresql"
    return False, ""


def main() -> None:
    settings = get_settings()
    if settings.app_env.lower() != "development":
        raise RuntimeError("The E2E server must run with APP_ENV=development")

    allowed, database_kind = _is_allowed_test_database(settings.database_url)
    if not allowed:
        raise RuntimeError(
            "E2E server only permits ./var/pravaah-e2e.sqlite3 or the local "
            "PostgreSQL database pravaah_e2e on 127.0.0.1:5432"
        )

    if database_kind == "sqlite":
        database_path = settings.database_url.removeprefix("sqlite:///")
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False},
        )
        try:
            Base.metadata.create_all(engine)
        finally:
            engine.dispose()
    else:
        # Apply the real migration chain against the isolated E2E database.
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    # Seed only synthetic development fixtures. This script refuses non-development use.
    seed_demo()
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.environ.get("PRAVAAH_API_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
