"""Database sessions.

Synchronous on purpose. psycopg's async mode cannot run on Windows' default
ProactorEventLoop, and FastAPI already runs `def` handlers in a threadpool, so sync sessions
cost nothing here and remove a whole class of event-loop problems.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _engine_url() -> str:
    url = str(get_settings().database_url)
    # Name the driver explicitly; psycopg2 is not installed.
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


engine = create_engine(_engine_url(), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
