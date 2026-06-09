"""Analyze drain: claim one user-enqueued `analyze_queued` file and run the AI-only enrich step."""

from __future__ import annotations

import os
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Callable, Optional

from sqlalchemy.orm import Session

from app.ai.base import AIConfigSnapshot
from app.models.book import BookRecord
from app.pipeline.process_file import AnalyzeRequest, analyze_file
from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentRun, EnrichmentTrigger
from db.models.file_record import FileRecord
from db.models.metadata import Metadata, MetadataSource
from db.repos import ai_config_repo, enrichment_run_repo, file_repo, metadata_repo
from db.repos.enrichment_run_repo import EnrichmentRunInput, EnrichmentRunResult
from db.session import get_session


SessionFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class DrainResult:
    """Outcome of one analyze-drain unit — surfaced for logging and tests."""

    file_id: int
    success: bool


def drain_one_analyze(session_factory: SessionFactory = get_session) -> Optional[DrainResult]:
    """Claim+analyze one `analyze_queued` file. None when the queue is empty (nothing to drain)."""
    claimed = _claim_one(session_factory)
    if claimed is None:
        return None

    succeeded = _run_analyze(claimed, session_factory)
    return DrainResult(file_id=claimed.file_id, success=succeeded)


@dataclass(frozen=True)
class _ClaimedFile:
    """A file already moved `analyze_queued→reading`, with the data needed for the AI call."""

    file_id: int
    directory_id: int
    record: BookRecord


def _claim_one(session_factory: SessionFactory) -> Optional[_ClaimedFile]:
    """Atomically claim one file and reconstruct its BookRecord from the persisted `file` snapshot."""
    with session_factory() as session:
        claimed = file_repo.claim_next_analyze_queued(session)
        if claimed is None:
            return None
        directory = session.get(Directory, claimed.directory_id)
        snapshot = metadata_repo.get_current(session, claimed.id, MetadataSource.file)
        record = _snapshot_to_book_record(claimed, directory, snapshot)
        return _ClaimedFile(
            file_id=claimed.id,
            directory_id=claimed.directory_id,
            record=record,
        )


def _run_analyze(claimed: _ClaimedFile, session_factory: SessionFactory) -> bool:
    """Resolve the open user_file run with active config, run the AI-only enrich, then close the run."""
    with session_factory() as session:
        active = ai_config_repo.get_active(session)
        if active is None:
            raise RuntimeError("no active AIConfigVersion — seed migration 011 must run before analyze")
        config = AIConfigSnapshot(
            system_prompt=active.system_prompt,
            cheap_model=active.cheap_model,
            expensive_model=active.expensive_model,
            escalation_threshold=float(active.escalation_threshold),
            response_format_ref=active.response_format_ref,
            provider=active.provider,
            effort=active.effort,
        )
        run = _resolve_run(session, claimed.directory_id)
        _stamp_config_version(session, run, active.id)
        session.commit()
        enrich_result = analyze_file(
            AnalyzeRequest(
                record=claimed.record,
                file_id=claimed.file_id,
                enrichment_run_id=run.id,
                session=session,
                config=config,
                config_version_id=active.id,
            )
        )
        if enrich_result.success:
            _finish_run(session, run.id)
        else:
            _fail_run(session, run.id)
        return enrich_result.success


def _resolve_run(session: Session, directory_id: int) -> EnrichmentRun:
    """Reuse the open user_file run, or open one for crash-recovered files. No config stamping, no commit."""
    run = enrichment_run_repo.find_latest_running(
        session, directory_id, EnrichmentTrigger.user_file
    )
    if run is not None:
        return run
    return enrichment_run_repo.create(
        session,
        EnrichmentRunInput(directory_id=directory_id, trigger=EnrichmentTrigger.user_file),
    )


def _stamp_config_version(session: Session, run: EnrichmentRun, config_version_id: int) -> None:
    """Record which active config version governs this run. Caller owns the commit boundary."""
    run.config_version_id = config_version_id
    session.flush()


def _finish_run(session: Session, run_id: int) -> None:
    enrichment_run_repo.finish(
        session,
        run_id,
        EnrichmentRunResult(success_count=1, failure_count=0),
    )
    session.commit()


def _fail_run(session: Session, run_id: int) -> None:
    enrichment_run_repo.fail(session, run_id, "analyze failed")
    session.commit()


def _snapshot_to_book_record(
    record: FileRecord,
    directory: Optional[Directory],
    snapshot: Optional[Metadata],
) -> BookRecord:
    """Rebuild the read-time BookRecord from its stored `file` snapshot — the AI call's input."""
    full_path = os.path.join(directory.path, record.filename) if directory else record.filename
    directories = [directory.name] if directory and directory.name else []
    if snapshot is None:
        return BookRecord(
            path=full_path,
            original_filename=record.filename,
            extension=(record.extension or "").lstrip("."),
            directories=directories,
            source="file",
        )
    snapshot_dict = snapshot.data if isinstance(snapshot.data, dict) else {}
    return BookRecord(
        path=full_path,
        original_filename=record.filename,
        extension=(record.extension or "").lstrip("."),
        directories=directories,
        title=snapshot.title,
        subtitle=snapshot.subtitle,
        authors=_string_list(snapshot_dict.get("authors")),
        description=_optional_string(snapshot_dict.get("description")),
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
        tags=_string_list(snapshot_dict.get("tags")),
        source="file",
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)
