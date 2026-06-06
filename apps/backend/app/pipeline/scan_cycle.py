"""One discover pass against a running ScanJob: walk filesystem, read file metadata (NO AI), reconcile FS↔DB."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.book import BookRecord
from app.pipeline.process_file import read_file_metadata
from app.scanner.db_scanner import DBScanner, ScanOutcome
from db.models.directory import Directory
from db.models.file_record import FileRecord
from db.repos import directory_repo, file_repo, scan_job_repo
from db.repos.scan_job_repo import ScanProgress
from db.session import get_session


SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class CycleResult:
    """Outcome of one discover pass — surfaced for logging and tests."""

    scan_job_id: int
    files_discovered: int
    files_read: int
    files_failed: int
    files_marked_missing: int
    directories_deleted: int
    directories_archived: int


def run_scan_cycle(
    scan_job_id: int,
    root_dir: str,
    session_factory: SessionFactory = get_session,
) -> CycleResult:
    """Execute one discover pass over `root_dir`, driving the already-running `scan_job_id` — NO AI."""
    # Driving the caller-provided id (not a fresh one) is what makes a UI-triggered discover
    # update the same job the API returned to the user.
    try:
        outcome = _walk_filesystem(root_dir, session_factory)
        files_discovered = len(outcome.file_ids_needing_read)
        _update_progress(session_factory, scan_job_id, ScanProgress(files_discovered=files_discovered))

        files_read, files_failed = _read_all_pending(
            outcome.file_ids_needing_read, session_factory, scan_job_id
        )
        marked_missing = _reconcile_files(root_dir, outcome, session_factory)
        deleted, archived = _reconcile_directories(root_dir, outcome, session_factory)

        _finish_scan_job(scan_job_id, session_factory)
        return CycleResult(
            scan_job_id=scan_job_id,
            files_discovered=files_discovered,
            files_read=files_read,
            files_failed=files_failed,
            files_marked_missing=marked_missing,
            directories_deleted=deleted,
            directories_archived=archived,
        )
    except Exception as exc:
        _fail_scan_job(scan_job_id, str(exc), session_factory)
        raise


def _walk_filesystem(root_dir: str, session_factory: SessionFactory) -> ScanOutcome:
    """Walk the tree and upsert Directory + FileRecord rows; return what was found on disk."""
    with session_factory() as session:
        scanner = DBScanner(session)
        scanner.scan(root_dir)
        return scanner.outcome


def _read_all_pending(
    file_ids: list[int], session_factory: SessionFactory, scan_job_id: int
) -> tuple[int, int]:
    """Read metadata for each new/changed/reappeared file (NO AI). Returns (read, failed)."""
    files_read = 0
    files_failed = 0
    files_attempted = 0
    for file_id in file_ids:
        _update_progress(session_factory, scan_job_id, ScanProgress(current_file_id=file_id))
        success = _read_one_file(file_id, session_factory)
        files_attempted += 1
        if success:
            files_read += 1
        else:
            files_failed += 1
        _update_progress(session_factory, scan_job_id, ScanProgress(files_processed=files_attempted))
    return files_read, files_failed


def _read_one_file(file_id: int, session_factory: SessionFactory) -> bool:
    """Open a per-file session and read its metadata into a `file` snapshot. Returns success flag."""
    with session_factory() as session:
        record = _load_book_record_for_file(session, file_id)
        if record is None:
            return False
        result = read_file_metadata(record=record, file_id=file_id, session=session)
        return result.success


def _reconcile_files(
    root_dir: str, outcome: ScanOutcome, session_factory: SessionFactory
) -> int:
    with session_factory() as session:
        return file_repo.mark_missing_under_root(
            session, root_dir, outcome.present_file_paths
        )


def _reconcile_directories(
    root_dir: str, outcome: ScanOutcome, session_factory: SessionFactory
) -> tuple[int, int]:
    with session_factory() as session:
        result = directory_repo.reconcile_missing_directories(
            session, root_dir, outcome.present_dir_paths
        )
        for anomaly_path in result.live_child_anomalies:
            print(f"[discover] gone dir kept active — live descendant remains: {anomaly_path}")
        return result.deleted, result.archived


def _load_book_record_for_file(session: Session, file_id: int) -> Optional[BookRecord]:
    record = session.get(FileRecord, file_id)
    if record is None:
        return None
    directory = session.get(Directory, record.directory_id)
    if directory is None:
        return None
    return _file_record_to_book_record(record, directory)


def _file_record_to_book_record(record: FileRecord, directory: Directory) -> BookRecord:
    full_path = os.path.join(directory.path, record.filename)
    return BookRecord(
        path=full_path,
        original_filename=record.filename,
        extension=(record.extension or "").lstrip("."),
        directories=[directory.name] if directory.name else [],
        source="file",
    )


def _update_progress(
    session_factory: SessionFactory, scan_job_id: int, progress: ScanProgress
) -> None:
    with session_factory() as session:
        scan_job_repo.update_progress(session, scan_job_id, progress)


def _finish_scan_job(scan_job_id: int, session_factory: SessionFactory) -> None:
    with session_factory() as session:
        scan_job_repo.finish(session, scan_job_id)


def _fail_scan_job(scan_job_id: int, message: str, session_factory: SessionFactory) -> None:
    with session_factory() as session:
        scan_job_repo.fail(session, scan_job_id, message)
