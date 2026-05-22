"""Apply an accepted AI suggestion: write metadata back, rename, move, snapshot, mark accepted."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.metadata.merge.book_record_merger import merge_book_records
from app.metadata.writer.registry import write_metadata
from app.models.book import BookRecord
import app.metadata.writer  # noqa: F401 — registers FB2/EPUB writers on import.
from app.move.mover import move_file
from app.naming.renamer import build_filename
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import ProcessingLogLevel, ProcessingStep
from db.repos import file_repo, log_repo, metadata_repo
from db.repos.log_repo import LogEntry
from db.repos.metadata_repo import MetadataInput, MetadataScalars


class AcceptError(Exception):
    """Raised when accepting a file cannot proceed (no AI suggestion, missing config, IO error)."""


@dataclass(frozen=True)
class AcceptResult:
    """Outcome of an accept operation — the persisted destination path of the file."""

    file_id: int
    final_path: Path


def accept_file(session: Session, file_id: int) -> AcceptResult:
    """Merge current ai+file metadata, write back, rename+move, snapshot, transition to accepted."""
    record = file_repo.get_by_id(session, file_id)
    if record is None:
        raise AcceptError(f"FileRecord {file_id} not found")

    ai_snapshot = metadata_repo.get_current(session, file_id, MetadataSource.ai)
    if ai_snapshot is None:
        raise AcceptError(f"FileRecord {file_id} has no current AI metadata to accept")

    file_snapshot = metadata_repo.get_current(session, file_id, MetadataSource.file)
    source_path = _build_source_path(record)
    merged = _merge_for_accept(source_path, record, file_snapshot, ai_snapshot)

    write_result = write_metadata(merged)
    if not write_result.success and not write_result.skipped:
        raise AcceptError(
            f"write_metadata failed for {source_path}: {'; '.join(write_result.errors)}"
        )

    final_path = _rename_and_move(source_path, merged)

    metadata_repo.create(session, _accepted_input(file_id, ai_snapshot, merged))
    file_repo.update_status(session, file_id, FileStatus.accepted)
    log_repo.write(
        session,
        LogEntry(
            file_id=file_id,
            step=ProcessingStep.write_back,
            level=ProcessingLogLevel.info,
            message=f"accepted; written to {final_path}",
        ),
    )
    return AcceptResult(file_id=file_id, final_path=final_path)


def _build_source_path(record: FileRecord) -> Path:
    return Path(record.directory.path) / record.filename


def _merge_for_accept(
    source_path: Path,
    record: FileRecord,
    file_snapshot: Optional[Metadata],
    ai_snapshot: Metadata,
) -> BookRecord:
    """AI fields win — `merge_book_records` already prioritizes source='ai' over 'file'."""
    inputs: list[BookRecord] = []
    if file_snapshot is not None:
        inputs.append(_snapshot_to_book_record(source_path, record, file_snapshot))
    inputs.append(_snapshot_to_book_record(source_path, record, ai_snapshot))
    merged = merge_book_records(inputs)
    merged.path = str(source_path)
    merged.original_filename = record.filename
    merged.extension = (record.extension or source_path.suffix.lstrip(".")).lower()
    return merged


def _snapshot_to_book_record(
    source_path: Path, record: FileRecord, snapshot: Metadata
) -> BookRecord:
    data = snapshot.data if isinstance(snapshot.data, dict) else {}
    authors = _string_list(data.get("authors"))
    tags = _string_list(data.get("tags"))
    description = _optional_string(data.get("description"))
    return BookRecord(
        path=str(source_path),
        original_filename=record.filename,
        extension=(record.extension or source_path.suffix.lstrip(".")).lower(),
        directories=_string_list(data.get("directories")),
        title=snapshot.title,
        subtitle=snapshot.subtitle,
        authors=authors,
        description=description,
        series=snapshot.series,
        series_index=snapshot.series_index,
        series_total=snapshot.series_total,
        language=snapshot.language,
        publisher=snapshot.publisher,
        isbn10=snapshot.isbn10,
        isbn13=snapshot.isbn13,
        asin=snapshot.asin,
        published=snapshot.published,
        year=snapshot.year,
        tags=tags,
        source=snapshot.source.value,
        confidence=float(snapshot.confidence) if snapshot.confidence is not None else None,
    )


def _rename_and_move(source_path: Path, merged: BookRecord) -> Path:
    template = os.environ.get("FILENAME_TEMPLATE")
    if not template:
        raise AcceptError("FILENAME_TEMPLATE is not set")
    target_dir_raw = os.environ.get("BOOKS_READY_DIR")
    if not target_dir_raw:
        raise AcceptError("BOOKS_READY_DIR is not set")

    base = build_filename(merged, template)
    filename = f"{base}.{merged.extension}"
    return move_file(source_path, Path(target_dir_raw), filename, subdirs=merged.directories)


def _accepted_input(
    file_id: int, ai_snapshot: Metadata, merged: BookRecord
) -> MetadataInput:
    data: dict[str, Any] = {
        "authors": list(merged.authors),
        "tags": list(merged.tags),
    }
    if merged.description is not None:
        data["description"] = merged.description
    scalars = MetadataScalars(
        title=merged.title,
        subtitle=merged.subtitle,
        language=merged.language,
        series=merged.series,
        series_index=merged.series_index,
        series_total=merged.series_total,
        publisher=merged.publisher,
        isbn13=merged.isbn13,
        isbn10=merged.isbn10,
        asin=merged.asin,
        published=_as_date(merged.published),
        year=merged.year,
        confidence=Decimal(str(merged.confidence)) if merged.confidence is not None else None,
    )
    return MetadataInput(
        file_id=file_id,
        source=MetadataSource.accepted,
        data=data,
        enrichment_run_id=ai_snapshot.enrichment_run_id,
        scalars=scalars,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float)) and str(item)]


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _as_date(value: Any) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    return None
