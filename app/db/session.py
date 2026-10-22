"""Database engine and request-scoped session dependency."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine():
    """Create one process-wide SQLAlchemy engine using configured database URL."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return a cached factory for non-autocommit, non-autoflush sessions."""
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it after the request."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
