"""Repository for directory_hints — enforces at most one is_current=True per directory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.models.directory_hint import DirectoryHint


@dataclass(frozen=True)
class DirectoryHintInput:
    """Payload for a new hint — directory binding, JSON body, optional AI provenance."""

    directory_id: int
    data: dict[str, Any]
    ai_model: Optional[str] = None
    prompt_version: Optional[str] = None


def create(session: Session, spec: DirectoryHintInput) -> DirectoryHint:
    """Insert a new hint as `is_current=True` and flip all prior rows for the directory to False."""
    session.execute(
        update(DirectoryHint)
        .where(
            DirectoryHint.directory_id == spec.directory_id,
            DirectoryHint.is_current.is_(True),
        )
        .values(is_current=False)
    )

    hint = DirectoryHint(
        directory_id=spec.directory_id,
        data=spec.data,
        ai_model=spec.ai_model,
        prompt_version=spec.prompt_version,
        is_current=True,
    )
    session.add(hint)
    session.flush()
    return hint


def get_current(session: Session, directory_id: int) -> Optional[DirectoryHint]:
    return session.execute(
        select(DirectoryHint).where(
            DirectoryHint.directory_id == directory_id,
            DirectoryHint.is_current.is_(True),
        )
    ).scalar_one_or_none()
