"""Repository for file_records — owns the FileStatus state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from db.repos._query_utils import subtree_clause


@dataclass(frozen=True)
class PaginatedRecords:
    """One page of FileRecord rows plus the total matching row count."""

    items: list[FileRecord]
    total: int


@dataclass(frozen=True)
class FileAttrs:
    """Optional scalar attributes used when creating a new FileRecord."""

    extension: Optional[str] = None
    format: Optional[str] = None
    size: Optional[int] = None
    hash: Optional[str] = None


# Legacy reading→ai_queued→enriching edges retained until their callers are
# removed; keeps the pipeline runnable during the phased refactor.
_ALLOWED_TRANSITIONS: dict[FileStatus, frozenset[FileStatus]] = {
    FileStatus.pending: frozenset(
        {FileStatus.reading, FileStatus.failed, FileStatus.missing}
    ),
    FileStatus.reading: frozenset(
        {
            FileStatus.read,
            FileStatus.ai_queued,
            FileStatus.enriching,
            FileStatus.enriched,
            FileStatus.failed,
        }
    ),
    FileStatus.read: frozenset(
        {
            FileStatus.reading,
            FileStatus.analyze_queued,
            FileStatus.failed,
            FileStatus.missing,
        }
    ),
    FileStatus.ai_queued: frozenset({FileStatus.enriching, FileStatus.failed}),
    FileStatus.analyze_queued: frozenset(
        {FileStatus.reading, FileStatus.enriching, FileStatus.failed}
    ),
    FileStatus.enriching: frozenset({FileStatus.enriched, FileStatus.failed}),
    FileStatus.enriched: frozenset(
        {
            FileStatus.accepted,
            FileStatus.rejected,
            FileStatus.analyze_queued,
            FileStatus.failed,
            FileStatus.missing,
        }
    ),
    FileStatus.accepted: frozenset({FileStatus.ai_queued, FileStatus.analyze_queued}),
    FileStatus.rejected: frozenset({FileStatus.ai_queued, FileStatus.analyze_queued}),
    FileStatus.failed: frozenset(
        {
            FileStatus.pending,
            FileStatus.ai_queued,
            FileStatus.analyze_queued,
            FileStatus.missing,
        }
    ),
    FileStatus.missing: frozenset({FileStatus.reading, FileStatus.read}),
}


class InvalidStatusTransition(ValueError):
    """Raised when update_status is called with a move not in the state machine."""

    def __init__(self, from_status: FileStatus, to_status: FileStatus):
        super().__init__(
            f"Invalid file status transition: {from_status.value} -> {to_status.value}"
        )
        self.from_status = from_status
        self.to_status = to_status


def transition(from_status: FileStatus, to_status: FileStatus) -> bool:
    """Pure predicate: True iff the move is allowed by the state machine."""
    if from_status == to_status:
        return True
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, frozenset())


def get_or_create(
    session: Session,
    directory_id: int,
    filename: str,
    attrs: Optional[FileAttrs] = None,
) -> FileRecord:
    existing = session.execute(
        select(FileRecord).where(
            FileRecord.directory_id == directory_id,
            FileRecord.filename == filename,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    extras = attrs or FileAttrs()
    record = FileRecord(
        directory_id=directory_id,
        filename=filename,
        extension=extras.extension,
        format=extras.format,
        size=extras.size,
        hash=extras.hash,
    )
    session.add(record)
    session.flush()
    return record


def update_status(
    session: Session,
    file_id: int,
    new_status: FileStatus,
    error_message: Optional[str] = None,
) -> FileRecord:
    """Apply a status change after validating against the state machine."""
    record = session.get(FileRecord, file_id)
    if record is None:
        raise LookupError(f"FileRecord {file_id} not found")

    if not transition(record.status, new_status):
        raise InvalidStatusTransition(record.status, new_status)

    record.status = new_status
    if error_message is not None or new_status == FileStatus.failed:
        record.error_message = error_message
    session.flush()
    return record


def claim_next_analyze_queued(session: Session) -> Optional[FileRecord]:
    """Atomically claim the oldest `analyze_queued` file (→`reading`) for the analyze drain; None if none."""
    # Status-guarded UPDATE + rowcount==1 is the race gate: only `analyze_queued` is ever
    # claimed — never `ai_queued`/`reading`/`enriching` — so no row is re-picked mid-pipeline.
    oldest_id = session.execute(
        select(FileRecord.id)
        .where(FileRecord.status == FileStatus.analyze_queued)
        .order_by(FileRecord.updated_at.asc(), FileRecord.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if oldest_id is None:
        return None

    claimed = session.execute(
        update(FileRecord)
        .where(
            FileRecord.id == oldest_id,
            FileRecord.status == FileStatus.analyze_queued,
        )
        .values(status=FileStatus.reading)
    )
    if claimed.rowcount != 1:
        return None

    record = session.get(FileRecord, oldest_id)
    session.refresh(record)  # bulk UPDATE bypassed the identity map — reload the new status
    return record


def get_by_directory(
    session: Session,
    directory_id: int,
    status: Optional[FileStatus] = None,
) -> list[FileRecord]:
    stmt = select(FileRecord).where(FileRecord.directory_id == directory_id)
    if status is not None:
        stmt = stmt.where(FileRecord.status == status)
    stmt = stmt.order_by(FileRecord.sort_order.asc(), FileRecord.filename.asc())
    return list(session.execute(stmt).scalars())


def get_by_id(session: Session, file_id: int) -> Optional[FileRecord]:
    """Return the FileRecord by primary key, or None if missing."""
    return session.get(FileRecord, file_id)


def list_paginated(
    session: Session,
    page: int,
    page_size: int,
    directory_id: Optional[int] = None,
    status: Optional[FileStatus] = None,
) -> PaginatedRecords:
    """Page over file_records, optionally narrowed by directory and/or status."""
    if page < 1:
        raise ValueError(f"page must be >= 1, got {page}")
    if page_size < 1:
        raise ValueError(f"page_size must be >= 1, got {page_size}")

    base = select(FileRecord)
    count_stmt = select(func.count()).select_from(FileRecord)
    if directory_id is not None:
        base = base.where(FileRecord.directory_id == directory_id)
        count_stmt = count_stmt.where(FileRecord.directory_id == directory_id)
    if status is not None:
        base = base.where(FileRecord.status == status)
        count_stmt = count_stmt.where(FileRecord.status == status)

    total = session.execute(count_stmt).scalar_one()
    rows = session.execute(
        base.order_by(FileRecord.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    return PaginatedRecords(items=list(rows), total=int(total))


# Durable `analyze_queued` is deliberately absent — it is the queue marker the
# drain re-claims after a restart, so a crash must not disturb it.
_STALLED_STATUSES = (FileStatus.reading, FileStatus.ai_queued, FileStatus.enriching)


def reset_stalled_to_analyze_queued(session: Session) -> int:
    """Crash recovery: re-queue in-flight FileRecord rows for analyze (bypasses state machine)."""
    result = session.execute(
        update(FileRecord)
        .where(FileRecord.status.in_(_STALLED_STATUSES))
        .values(status=FileStatus.analyze_queued, error_message=None)
    )
    session.flush()
    return result.rowcount or 0


def list_directories_with_pending(session: Session) -> list[Directory]:
    """Return distinct Directory rows that own at least one pending FileRecord."""
    stmt = (
        select(Directory)
        .join(FileRecord, FileRecord.directory_id == Directory.id)
        .where(FileRecord.status == FileStatus.pending)
        .distinct()
        .order_by(Directory.path.asc())
    )
    return list(session.execute(stmt).scalars())


def count_by_status(session: Session, status: FileStatus) -> int:
    """Return the total number of FileRecord rows in a given status."""
    stmt = select(func.count()).select_from(FileRecord).where(FileRecord.status == status)
    return int(session.execute(stmt).scalar_one())


# A file in any of these states left disk *unexpectedly*; `accepted`/`rejected`
# moved on purpose and in-flight rows are mid-transition, so neither is missing.
_RECONCILABLE_TO_MISSING = (
    FileStatus.read,
    FileStatus.enriched,
    FileStatus.failed,
)


def mark_missing_under_root(
    session: Session, root_path: str, present_paths: set[str]
) -> int:
    """Mark reconcilable files under `root_path` whose on-disk path is absent as `missing`."""
    rows = session.execute(
        select(FileRecord, Directory.path)
        .join(Directory, FileRecord.directory_id == Directory.id)
        .where(
            subtree_clause(root_path),
            FileRecord.status.in_(_RECONCILABLE_TO_MISSING),
        )
    ).all()

    marked = 0
    for record, directory_path in rows:
        full_path = directory_path + "/" + record.filename
        if full_path in present_paths:
            continue
        update_status(session, record.id, FileStatus.missing)
        marked += 1
    session.flush()
    return marked
