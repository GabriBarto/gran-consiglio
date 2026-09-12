"""
SQLAlchemy engine/session setup for the real database (see
backend/db/projectwork_en_v2.sql for the schema this maps to, and
app/db/models.py for the mapping). This module never creates or alters
schema (no `Base.metadata.create_all()` anywhere) — the .sql file is the
single source of truth for table structure; SQLAlchemy here is purely a
mapping/query layer on top of tables that already exist.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session: commits on success, rolls back on any
    exception, always closes. Usage: `with get_session() as session: ...`."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
