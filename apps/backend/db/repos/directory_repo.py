"""Repository for the directories table."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus


@dataclass(frozen=True)
class DirectoryInput:
    """Identity tuple for `get_or_create`. `path` is unique; the rest is set on insert."""

    path: str
    name: str
    parent_id: Optional[int]
    depth: int


@dataclass(frozen=True)
class DirectoryStats:
    """Per-directory file counts grouped by the statuses surfaced in the UI."""

    file_count: int
    pending_count: int
    enriched_count: int
    accepted_count: int
    missing_count: int


_EMPTY_STATS = DirectoryStats(0, 0, 0, 0, 0)


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


def get_by_id(session: Session, directory_id: int) -> Optional[Directory]:
    return session.get(Directory, directory_id)


def get_status_counts(session: Session) -> dict[int, DirectoryStats]:
    """Aggregate file counts per directory in a single query — keyed by directory_id."""
    rows = session.execute(
        select(
            FileRecord.directory_id,
            FileRecord.status,
            func.count(FileRecord.id),
        ).group_by(FileRecord.directory_id, FileRecord.status)
    ).all()

    pending: dict[int, int] = {}
    enriched: dict[int, int] = {}
    accepted: dict[int, int] = {}
    missing: dict[int, int] = {}
    totals: dict[int, int] = {}
    for directory_id, status, count in rows:
        totals[directory_id] = totals.get(directory_id, 0) + count
        if status == FileStatus.pending:
            pending[directory_id] = count
        elif status == FileStatus.enriched:
            enriched[directory_id] = count
        elif status == FileStatus.accepted:
            accepted[directory_id] = count
        elif status == FileStatus.missing:
            missing[directory_id] = count

    return {
        directory_id: DirectoryStats(
            file_count=totals[directory_id],
            pending_count=pending.get(directory_id, 0),
            enriched_count=enriched.get(directory_id, 0),
            accepted_count=accepted.get(directory_id, 0),
            missing_count=missing.get(directory_id, 0),
        )
        for directory_id in totals
    }


def stats_for(stats: dict[int, DirectoryStats], directory_id: int) -> DirectoryStats:
    """Lookup helper — returns zeroed stats when a directory has no files yet."""
    return stats.get(directory_id, _EMPTY_STATS)


def get_stats_for_directory(session: Session, directory_id: int) -> DirectoryStats:
    """Scoped variant of `get_status_counts` for a single directory."""
    rows = session.execute(
        select(FileRecord.status, func.count(FileRecord.id))
        .where(FileRecord.directory_id == directory_id)
        .group_by(FileRecord.status)
    ).all()

    by_status = {status_value: count for status_value, count in rows}
    return DirectoryStats(
        file_count=sum(by_status.values()),
        pending_count=by_status.get(FileStatus.pending, 0),
        enriched_count=by_status.get(FileStatus.enriched, 0),
        accepted_count=by_status.get(FileStatus.accepted, 0),
        missing_count=by_status.get(FileStatus.missing, 0),
    )
