"""Start a disposable SQLite-backed API for real browser integration tests.

This entry point is intended for local/CI E2E only. It never connects to the
configured production database: Playwright supplies an isolated SQLite URL.
"""
from __future__ import annotations

import os
from pathlib import Path

import uvicorn
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.db.base import Base
import app.models  # noqa: F401  Ensure every mapped model is registered before create_all.
from scripts.seed_demo import main as seed_demo


def main() -> None:
    settings = get_settings()
    if settings.app_env.lower() != "development":
        raise RuntimeError("The E2E server must run with APP_ENV=development")
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("The E2E server only permits a disposable SQLite database")

    database_path = settings.database_url.removeprefix("sqlite:///")
    if database_path != ":memory:":
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    engine.dispose()

    # Seed only synthetic development fixtures. This script refuses non-development use.
    seed_demo()
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("PRAVAAH_API_PORT", "8000")))


if __name__ == "__main__":
    main()
