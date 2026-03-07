"""Engine and session factory. Uses DATABASE_URL from environment."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.base import Base

_DEFAULT_URL = "mysql+pymysql://ebook:ebook@localhost:3306/ebook_meta"


def get_database_url() -> str:
    """Read DATABASE_URL from environment or return default for local MariaDB."""
    return os.environ.get("DATABASE_URL", _DEFAULT_URL)


def create_engine_from_env():
    """Build engine from DATABASE_URL. Echo SQL when DEBUG=1."""
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
