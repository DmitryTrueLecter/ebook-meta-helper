"""FastAPI dependencies."""

from typing import Generator

from sqlalchemy.orm import Session

from db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session for the request; close on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
