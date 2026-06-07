"""Directory tree, directory detail with file list, and discover-trigger endpoint."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.projections import to_scan_status
from app.api.schemas import (
    DirectoryDetail,
    DirectoryNode,
    FileListItem,
    ScanJobProgress,
)
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from db.repos import directory_repo, file_repo, metadata_repo, scan_job_repo
from db.repos.directory_repo import DirectoryStats

router = APIRouter(prefix="/api/directories", tags=["directories"])


@router.get("", response_model=list[DirectoryNode])
def list_directory_tree(
    include_missing: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> list[DirectoryNode]:
    """Directory tree with per-directory counts; archived (`missing`) directories hidden unless `include_missing`."""
    directories = (
        directory_repo.get_tree_including_missing(db)
        if include_missing
        else directory_repo.get_tree(db)
    )
    stats_by_id = directory_repo.get_status_counts(db)
    visible_ids = {d.id for d in directories}
    roots = [d for d in directories if d.parent_id is None or d.parent_id not in visible_ids]
    return [_to_node(root, stats_by_id, visible_ids) for root in roots]


@router.get("/{directory_id}", response_model=DirectoryDetail)
def get_directory_detail(
    directory_id: int,
    status_filter: Optional[str] = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> DirectoryDetail:
    """Single directory with its file list — optional `?status=<FileStatus>` filter."""
    directory = directory_repo.get_by_id(db, directory_id)
    if directory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory {directory_id} not found",
        )

    file_status = _parse_status_filter(status_filter)
    files = _list_files(db, directory_id, file_status)
    stats = directory_repo.get_stats_for_directory(db, directory_id)
    return _to_detail(directory, stats, files)


@router.post(
    "/{directory_id}/discover",
    response_model=ScanJobProgress,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_directory_discover(
    directory_id: int, db: Session = Depends(get_db)
) -> ScanJobProgress:
    """Enqueue a discover job (FS↔DB sync + read file metadata, NO AI); watcher runs it."""
    directory = directory_repo.get_by_id(db, directory_id)
    if directory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory {directory_id} not found",
        )

    active = scan_job_repo.find_active_or_pending(db)
    if active is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Discover job {active.id} is already {active.status.value}",
        )

    job = scan_job_repo.create(
        db, root_path=directory.path, root_directory_id=directory.id
    )
    db.commit()
    return to_scan_status(job)


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


def _list_files(
    db: Session, directory_id: int, file_status: Optional[FileStatus]
) -> list[FileListItem]:
    records = file_repo.get_by_directory(db, directory_id, file_status)
    ai_ids = metadata_repo.find_files_with_ai_suggestion(db, [r.id for r in records])
    return [_to_list_item(record, has_ai=record.id in ai_ids) for record in records]


def _to_node(
    directory: Directory,
    stats_by_id: dict[int, DirectoryStats],
    visible_ids: set[int],
) -> DirectoryNode:
    stats = directory_repo.stats_for(stats_by_id, directory.id)
    children = [
        _to_node(child, stats_by_id, visible_ids)
        for child in directory.children
        if child.id in visible_ids
    ]
    return DirectoryNode(
        id=directory.id,
        name=directory.name,
        path=directory.path,
        depth=directory.depth,
        status=directory.status,
        file_count=stats.file_count,
        pending_count=stats.pending_count,
        enriched_count=stats.enriched_count,
        accepted_count=stats.accepted_count,
        missing_count=stats.missing_count,
        children=children,
    )


def _to_detail(
    directory: Directory, stats: DirectoryStats, files: list[FileListItem]
) -> DirectoryDetail:
    return DirectoryDetail(
        id=directory.id,
        name=directory.name,
        path=directory.path,
        depth=directory.depth,
        file_count=stats.file_count,
        pending_count=stats.pending_count,
        enriched_count=stats.enriched_count,
        accepted_count=stats.accepted_count,
        files=files,
    )


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
