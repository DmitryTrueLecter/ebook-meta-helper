"""One scan pass against an already-running ScanJob: walk filesystem, summarize per directory, process each file."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session

import app.ai.providers  # noqa: F401 - triggers provider registration
from app.ai.registry import get as get_provider
from app.models.book import BookRecord
from app.pipeline.process_file import process_file
from app.scanner.db_scanner import DBScanner
from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentTrigger
from db.models.file_record import FileRecord, FileStatus
from db.repos import (
    directory_hint_repo,
    enrichment_run_repo,
    file_repo,
    scan_job_repo,
)
from db.repos.directory_hint_repo import DirectoryHintInput
from db.repos.enrichment_run_repo import EnrichmentRunInput, EnrichmentRunResult
from db.repos.scan_job_repo import ScanProgress
from db.session import get_session


SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class CycleResult:
    """Outcome of one scan pass — surfaced for logging and tests."""

    scan_job_id: int
    files_discovered: int
    files_processed: int
    files_failed: int


@dataclass(frozen=True)
class _DirectoryHintRef:
    """A directory hint paired with the row id it was persisted under (None if no hint)."""

    data: Optional[dict]
    row_id: Optional[int]


@dataclass(frozen=True)
class _CycleContext:
    """Execution context threaded through the per-directory and per-file work."""

    scan_job_id: int
    provider_name: str
    session_factory: "SessionFactory"


def run_scan_cycle(
    scan_job_id: int,
    root_dir: str,
    session_factory: SessionFactory = get_session,
) -> CycleResult:
    """Execute one full DB-driven scan over `root_dir`, driving the already-running `scan_job_id`."""
    # Driving the caller-provided id (not a fresh one) is what makes a UI-triggered scan
    # update the same job the API returned to the user.
    try:
        # Inside the try so a missing AI_PROVIDER fails the pre-claimed job instead of
        # leaving it stuck `running` forever and 409-ing every later scan.
        provider_name = _require_env("AI_PROVIDER")
        ctx = _CycleContext(
            scan_job_id=scan_job_id,
            provider_name=provider_name,
            session_factory=session_factory,
        )

        _populate_filesystem_state(root_dir, session_factory)
        directory_ids = _collect_pending_directory_ids(session_factory)
        files_discovered = _count_pending(session_factory)
        _update_progress(ctx, ScanProgress(files_discovered=files_discovered))

        files_processed, files_failed = _process_all_directories(ctx, directory_ids)

        _finish_scan_job(scan_job_id, session_factory)
        return CycleResult(
            scan_job_id=scan_job_id,
            files_discovered=files_discovered,
            files_processed=files_processed,
            files_failed=files_failed,
        )
    except Exception as exc:
        _fail_scan_job(scan_job_id, str(exc), session_factory)
        raise


def _populate_filesystem_state(root_dir: str, session_factory: SessionFactory) -> None:
    """Walk the filesystem and upsert Directory + FileRecord rows. New files default to `pending`."""
    with session_factory() as session:
        DBScanner(session).scan(root_dir)


def _collect_pending_directory_ids(session_factory: SessionFactory) -> list[int]:
    """Snapshot the directory id list so per-directory work below can use fresh sessions."""
    with session_factory() as session:
        return [d.id for d in file_repo.list_directories_with_pending(session)]


def _count_pending(session_factory: SessionFactory) -> int:
    with session_factory() as session:
        return file_repo.count_by_status(session, FileStatus.pending)


def _process_all_directories(
    ctx: _CycleContext, directory_ids: list[int]
) -> tuple[int, int]:
    files_processed = 0
    files_failed = 0
    for directory_id in directory_ids:
        hint = _summarize_and_store_hint(ctx, directory_id)
        pending_file_ids = _snapshot_pending_file_ids(directory_id, ctx.session_factory)
        for file_id in pending_file_ids:
            success = _process_one_file(ctx, directory_id=directory_id, file_id=file_id, hint=hint)
            files_processed += 1
            if not success:
                files_failed += 1
            _update_progress(ctx, ScanProgress(files_processed=files_processed))
    return files_processed, files_failed


def _summarize_and_store_hint(ctx: _CycleContext, directory_id: int) -> _DirectoryHintRef:
    """Build BookRecord list, call provider.summarize_directory, persist DirectoryHint."""
    records = _load_pending_book_records(directory_id, ctx.session_factory)
    if not records:
        return _DirectoryHintRef(data=None, row_id=None)

    provider = get_provider(ctx.provider_name)
    hint_data = provider.summarize_directory(records)

    with ctx.session_factory() as session:
        hint = directory_hint_repo.create(
            session,
            DirectoryHintInput(
                directory_id=directory_id, data=hint_data, ai_model=ctx.provider_name
            ),
        )
        return _DirectoryHintRef(data=hint_data, row_id=hint.id)


def _snapshot_pending_file_ids(directory_id: int, session_factory: SessionFactory) -> list[int]:
    with session_factory() as session:
        files = file_repo.get_by_directory(session, directory_id, status=FileStatus.pending)
        return [f.id for f in files]


def _load_pending_book_records(directory_id: int, session_factory: SessionFactory) -> list[BookRecord]:
    """Read DB rows and convert to BookRecord — the AI provider input shape."""
    with session_factory() as session:
        directory = session.get(Directory, directory_id)
        if directory is None:
            return []
        files = file_repo.get_by_directory(session, directory_id, status=FileStatus.pending)
        return [_file_record_to_book_record(f, directory) for f in files]


def _file_record_to_book_record(record: FileRecord, directory: Directory) -> BookRecord:
    full_path = os.path.join(directory.path, record.filename)
    return BookRecord(
        path=full_path,
        original_filename=record.filename,
        extension=(record.extension or "").lstrip("."),
        directories=[directory.name] if directory.name else [],
        source="file",
    )


def _process_one_file(
    ctx: _CycleContext,
    *,
    directory_id: int,
    file_id: int,
    hint: _DirectoryHintRef,
) -> bool:
    """Open a per-file session and run process_file inside an EnrichmentRun. Returns success flag."""
    _update_progress(ctx, ScanProgress(current_file_id=file_id))

    with ctx.session_factory() as session:
        run = enrichment_run_repo.create(
            session,
            EnrichmentRunInput(
                directory_id=directory_id,
                trigger=EnrichmentTrigger.scan,
                ai_model=ctx.provider_name,
            ),
        )
        if hint.row_id is not None:
            run.directory_hint_id = hint.row_id
        run.file_count = 1
        session.flush()
        session.commit()

        record = _load_book_record_for_file(session, file_id)
        if record is None:
            enrichment_run_repo.fail(session, run.id, "FileRecord vanished before processing")
            return False

        result = process_file(
            record=record,
            file_id=file_id,
            enrichment_run_id=run.id,
            directory_hint=hint.data,
            session=session,
        )

        outcome = (
            EnrichmentRunResult(success_count=1, failure_count=0)
            if result.success
            else EnrichmentRunResult(success_count=0, failure_count=1)
        )
        enrichment_run_repo.finish(session, run.id, outcome)
        return result.success


def _load_book_record_for_file(session: Session, file_id: int) -> Optional[BookRecord]:
    record = session.get(FileRecord, file_id)
    if record is None:
        return None
    directory = session.get(Directory, record.directory_id)
    if directory is None:
        return None
    return _file_record_to_book_record(record, directory)


def _update_progress(ctx: _CycleContext, progress: ScanProgress) -> None:
    with ctx.session_factory() as session:
        scan_job_repo.update_progress(session, ctx.scan_job_id, progress)


def _finish_scan_job(scan_job_id: int, session_factory: SessionFactory) -> None:
    with session_factory() as session:
        scan_job_repo.finish(session, scan_job_id)


def _fail_scan_job(scan_job_id: int, message: str, session_factory: SessionFactory) -> None:
    with session_factory() as session:
        scan_job_repo.fail(session, scan_job_id, message)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value
