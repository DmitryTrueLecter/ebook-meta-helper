"""Repository for the directories table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from db.models.directory import Directory


@dataclass(frozen=True)
class DirectoryInput:
    """Identity tuple for `get_or_create`. `path` is unique; the rest is set on insert."""

    path: str
    name: str
    parent_id: Optional[int]
    depth: int


def get_or_create(session: Session, spec: DirectoryInput) -> Directory:
    existing = session.execute(
        select(Directory).where(Directory.path == spec.path)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    directory = Directory(
        path=spec.path,
        name=spec.name,
        parent_id=spec.parent_id,
        depth=spec.depth,
    )
    session.add(directory)
    session.flush()
    return directory


def update_file_count(session: Session, directory_id: int, delta: int) -> None:
    directory = session.get(Directory, directory_id)
    if directory is None:
        raise LookupError(f"Directory {directory_id} not found")
    directory.file_count = (directory.file_count or 0) + delta
    session.flush()


def set_last_scanned(session: Session, directory_id: int) -> None:
    directory = session.get(Directory, directory_id)
    if directory is None:
        raise LookupError(f"Directory {directory_id} not found")
    directory.last_scanned_at = datetime.now()
    session.flush()


def get_tree(session: Session) -> list[Directory]:
    """Return all directories with `children` eagerly loaded; roots first."""
    return list(
        session.execute(
            select(Directory)
            .options(selectinload(Directory.children))
            .order_by(Directory.depth.asc(), Directory.path.asc())
        ).scalars()
    )
