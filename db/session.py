"""Engine and session factory. Uses DATABASE_URL or DB_* components from environment."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.base import Base


def get_database_url() -> str:
    """Build database URL from environment.
    
    Priority:
    1. DATABASE_URL if set
    2. Construct from DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    """
    if url := os.environ.get("DATABASE_URL"):
        return url

    user = os.environ.get("DB_USER", "ebook")
    password = os.environ.get("DB_PASSWORD", "ebook")
    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "ebook_meta")

    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}"


def create_engine_from_env():
    """Build engine from DB config. Echo SQL when DEBUG=1."""
    url = get_database_url()
    echo = os.environ.get("DEBUG", "").strip() in ("1", "true", "yes")
    return create_engine(url, echo=echo, future=True)


engine = create_engine_from_env()
SessionLocal = sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Context manager for a DB session. Commits on success, rolls back on exception."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Prefer Alembic migrations in production."""
    Base.metadata.create_all(bind=engine)
