"""Repository for file_records — owns the FileStatus state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models.file_record import FileRecord, FileStatus


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


# State machine: see invariant tests for the full allowed-edge list.
_ALLOWED_TRANSITIONS: dict[FileStatus, frozenset[FileStatus]] = {
    FileStatus.pending: frozenset({FileStatus.reading, FileStatus.failed}),
    FileStatus.reading: frozenset(
        {FileStatus.ai_queued, FileStatus.enriched, FileStatus.failed}
    ),
    FileStatus.ai_queued: frozenset({FileStatus.enriching, FileStatus.failed}),
    FileStatus.enriching: frozenset({FileStatus.enriched, FileStatus.failed}),
    FileStatus.enriched: frozenset(
        {FileStatus.accepted, FileStatus.rejected, FileStatus.failed}
    ),
    FileStatus.accepted: frozenset({FileStatus.ai_queued}),
    FileStatus.rejected: frozenset({FileStatus.ai_queued}),
    FileStatus.failed: frozenset({FileStatus.pending, FileStatus.ai_queued}),
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
