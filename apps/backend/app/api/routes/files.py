"""Files API: paginated list, detail, metadata history, logs, accept, reject, enrich."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import (
    EnrichmentTriggerResponse,
    FileDetail,
    FileListItem,
    MetadataSnapshot,
    PaginatedFiles,
    ProcessingLogEntry,
)
from app.pipeline.accept_file import AcceptError, accept_file
from db.models.enrichment_run import EnrichmentTrigger
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import ProcessingLog
from db.repos import (
    enrichment_run_repo,
    file_repo,
    log_repo,
    metadata_repo,
)
from db.repos.enrichment_run_repo import EnrichmentRunInput
from db.repos.file_repo import InvalidStatusTransition

router = APIRouter(prefix="/api/files", tags=["files"])

_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200


@router.get("", response_model=PaginatedFiles)
def list_files(
    directory_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=_DEFAULT_PAGE_SIZE, ge=1, le=_MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
) -> PaginatedFiles:
    """Paginated file listing with optional `directory_id` and `status` filters."""
    file_status = _parse_status_filter(status_filter)
    page_data = file_repo.list_paginated(
        db,
        page=page,
        page_size=page_size,
        directory_id=directory_id,
        status=file_status,
    )
    ai_ids = metadata_repo.find_files_with_ai_suggestion(
        db, [record.id for record in page_data.items]
    )
    items = [_to_list_item(record, has_ai=record.id in ai_ids) for record in page_data.items]
    return PaginatedFiles(items=items, total=page_data.total, page=page, page_size=page_size)


@router.get("/{file_id}", response_model=FileDetail)
def get_file_detail(file_id: int, db: Session = Depends(get_db)) -> FileDetail:
    """Single file with the current `file` and `ai` metadata snapshots projected."""
    record = _require_file(db, file_id)
    file_snapshot = metadata_repo.get_current(db, file_id, MetadataSource.file)
    ai_snapshot = metadata_repo.get_current(db, file_id, MetadataSource.ai)
    return _to_detail(record, file_snapshot, ai_snapshot)


@router.get("/{file_id}/metadata", response_model=list[MetadataSnapshot])
def list_file_metadata(file_id: int, db: Session = Depends(get_db)) -> list[MetadataSnapshot]:
    """Full metadata history for the file — newest first."""
    _require_file(db, file_id)
    history = metadata_repo.get_history(db, file_id)
    return [_to_metadata_snapshot(row) for row in history]


@router.get("/{file_id}/logs", response_model=list[ProcessingLogEntry])
def list_file_logs(
    file_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[ProcessingLogEntry]:
    """Last `limit` processing-log entries for the file — newest first (capped at 200)."""
    _require_file(db, file_id)
    entries = log_repo.get_for_file(db, file_id, limit=limit)
    return [_to_log_entry(row) for row in entries]


@router.post("/{file_id}/accept", response_model=FileListItem)
def accept_file_endpoint(file_id: int, db: Session = Depends(get_db)) -> FileListItem:
    """Apply the current AI suggestion — write metadata back, rename, move, snapshot, mark accepted."""
    _require_file(db, file_id)
    try:
        accept_file(db, file_id)
    except (AcceptError, InvalidStatusTransition) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    db.commit()
    record = _require_file(db, file_id)
    return _to_list_item(record, has_ai=True)


@router.post("/{file_id}/reject", response_model=FileListItem)
def reject_file_endpoint(file_id: int, db: Session = Depends(get_db)) -> FileListItem:
    """Mark the file as rejected without touching the file on disk."""
    record = _require_file(db, file_id)
    try:
        record = file_repo.update_status(db, file_id, FileStatus.rejected)
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    db.commit()
    ai_ids = metadata_repo.find_files_with_ai_suggestion(db, [file_id])
    return _to_list_item(record, has_ai=file_id in ai_ids)


@router.post(
    "/{file_id}/enrich",
    response_model=EnrichmentTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enrich_file_endpoint(
    file_id: int, db: Session = Depends(get_db)
) -> EnrichmentTriggerResponse:
    """Queue the file for AI re-enrichment — watcher picks up `ai_queued` rows on the next cycle."""
    record = _require_file(db, file_id)
    directory_id = record.directory_id
    try:
        updated = file_repo.update_status(db, file_id, FileStatus.ai_queued)
    except InvalidStatusTransition as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    run = enrichment_run_repo.create(
        db,
        EnrichmentRunInput(
            directory_id=directory_id, trigger=EnrichmentTrigger.user_file
        ),
    )
    db.commit()
    return EnrichmentTriggerResponse(
        enrichment_run_id=run.id, file_id=file_id, status=updated.status.value
    )


def _require_file(db: Session, file_id: int) -> FileRecord:
    record = file_repo.get_by_id(db, file_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found",
        )
    return record


def _parse_status_filter(raw: Optional[str]) -> Optional[FileStatus]:
    if raw is None or raw == "":
        return None
    try:
        return FileStatus(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status filter: {raw}",
        ) from exc


def _to_list_item(record: FileRecord, has_ai: bool) -> FileListItem:
    return FileListItem(
        id=record.id,
        filename=record.filename,
        extension=record.extension,
        format=record.format,
        status=record.status.value,
        has_ai_suggestion=has_ai,
        sort_order=float(record.sort_order) if record.sort_order is not None else None,
    )


def _to_detail(
    record: FileRecord,
    file_snapshot: Optional[Metadata],
    ai_snapshot: Optional[Metadata],
) -> FileDetail:
    return FileDetail(
        id=record.id,
        directory_id=record.directory_id,
        filename=record.filename,
        extension=record.extension,
        format=record.format,
        status=record.status.value,
        sort_order=float(record.sort_order) if record.sort_order is not None else None,
        error_message=record.error_message,
        file_metadata=_to_metadata_snapshot(file_snapshot) if file_snapshot else None,
        ai_metadata=_to_metadata_snapshot(ai_snapshot) if ai_snapshot else None,
    )


def _to_metadata_snapshot(row: Metadata) -> MetadataSnapshot:
    return MetadataSnapshot(
        id=row.id,
        source=row.source.value,
        is_current=row.is_current,
        title=row.title,
        subtitle=row.subtitle,
        language=row.language,
        series=row.series,
        series_index=row.series_index,
        isbn13=row.isbn13,
        confidence=float(row.confidence) if row.confidence is not None else None,
        data=row.data if isinstance(row.data, dict) else {},
        created_at=row.created_at,
    )


def _to_log_entry(row: ProcessingLog) -> ProcessingLogEntry:
    return ProcessingLogEntry(
        step=row.step.value,
        level=row.level.value,
        message=row.message or "",
        duration_ms=row.duration_ms,
        created_at=row.created_at,
    )
