"""Pipeline: read embedded metadata, AI-enrich, persist snapshots and step logs."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.ai.enrich import enrich
from app.metadata.cleaner import clean_record
from app.metadata.reader.registry import read_metadata
from app.models.book import BookRecord
from app.models.pipeline import PipelineResult
from db.models.file_record import FileStatus
from db.models.metadata import MetadataSource
from db.models.processing_log import ProcessingLogLevel, ProcessingStep
from db.repos import file_repo, log_repo, metadata_repo
from db.repos.log_repo import LogEntry
from db.repos.metadata_repo import MetadataInput, MetadataScalars


@dataclass(frozen=True)
class _StepContext:
    file_id: int
    enrichment_run_id: Optional[int]
    session: Session


# DEV-FN-SHAPE waiver: 5-param signature is a public contract from the architect's
# spec — caller passes a per-file context the function cannot synthesize itself.
def process_file(
    record: BookRecord,
    file_id: int,
    enrichment_run_id: int,
    directory_hint: dict | None,
    session: Session,
) -> PipelineResult:
    """Step boundaries commit so AI/network work runs outside an open transaction."""
    ctx = _StepContext(file_id=file_id, enrichment_run_id=enrichment_run_id, session=session)

    after_reading = _run_reading(record, ctx)
    if not after_reading.success:
        return after_reading

    return _run_enriching(after_reading.record, directory_hint, ctx)


def read_file_metadata(
    record: BookRecord,
    file_id: int,
    session: Session,
) -> PipelineResult:
    """Discover read: read metadata FROM the file (NO AI), persist the `file` snapshot, land `read`."""
    ctx = _StepContext(file_id=file_id, enrichment_run_id=None, session=session)
    file_repo.update_status(ctx.session, ctx.file_id, FileStatus.reading)

    try:
        read_result = read_metadata(record)
        cleaned = clean_record(read_result)
    except Exception as exc:
        return _fail(ctx, ProcessingStep.read_metadata, exc)

    try:
        metadata_repo.create(
            ctx.session,
            MetadataInput(
                file_id=ctx.file_id,
                source=MetadataSource.file,
                data=_record_to_data(cleaned),
                scalars=_record_to_scalars(cleaned),
            ),
        )
        file_repo.update_status(ctx.session, ctx.file_id, FileStatus.read)
        log_repo.write(
            ctx.session,
            LogEntry(
                file_id=ctx.file_id,
                step=ProcessingStep.read_metadata,
                level=ProcessingLogLevel.info,
                message="file metadata read and stored",
            ),
        )
        ctx.session.commit()
    except Exception as exc:
        return _fail(ctx, ProcessingStep.read_metadata, exc)

    return PipelineResult(success=True, record=cleaned)


def _run_reading(record: BookRecord, ctx: _StepContext) -> PipelineResult:
    file_repo.update_status(ctx.session, ctx.file_id, FileStatus.reading)

    try:
        read_result = read_metadata(record)
        cleaned = clean_record(read_result)
    except Exception as exc:
        return _fail(ctx, ProcessingStep.read_metadata, exc)

    try:
        metadata_repo.create(
            ctx.session,
            MetadataInput(
                file_id=ctx.file_id,
                source=MetadataSource.file,
                data=_record_to_data(cleaned),
                scalars=_record_to_scalars(cleaned),
            ),
        )
        file_repo.update_status(ctx.session, ctx.file_id, FileStatus.ai_queued)
        log_repo.write(
            ctx.session,
            LogEntry(
                file_id=ctx.file_id,
                enrichment_run_id=ctx.enrichment_run_id,
                step=ProcessingStep.read_metadata,
                level=ProcessingLogLevel.info,
                message="file metadata read and stored",
            ),
        )
        ctx.session.commit()
    except Exception as exc:
        return _fail(ctx, ProcessingStep.read_metadata, exc)

    return PipelineResult(success=True, record=cleaned)


def _run_enriching(
    record: BookRecord,
    directory_hint: dict | None,
    ctx: _StepContext,
) -> PipelineResult:
    file_repo.update_status(ctx.session, ctx.file_id, FileStatus.enriching)
    ctx.session.commit()  # release the lock before the network call

    try:
        provider_name = os.environ.get("AI_PROVIDER")
        if not provider_name:
            raise RuntimeError("AI_PROVIDER is not set")
        ai_record = enrich(record, provider_name=provider_name, directory_hint=directory_hint)
        cleaned = clean_record(ai_record)
    except Exception as exc:
        return _fail(ctx, ProcessingStep.ai_enrich, exc)

    try:
        metadata_repo.create(
            ctx.session,
            MetadataInput(
                file_id=ctx.file_id,
                source=MetadataSource.ai,
                data=_record_to_data(cleaned),
                enrichment_run_id=ctx.enrichment_run_id,
                scalars=_record_to_scalars(cleaned),
            ),
        )
        file_repo.update_status(ctx.session, ctx.file_id, FileStatus.enriched)
        log_repo.write(
            ctx.session,
            LogEntry(
                file_id=ctx.file_id,
                enrichment_run_id=ctx.enrichment_run_id,
                step=ProcessingStep.ai_enrich,
                level=ProcessingLogLevel.info,
                message="AI enrichment stored",
            ),
        )
        ctx.session.commit()
    except Exception as exc:
        return _fail(ctx, ProcessingStep.ai_enrich, exc)

    return PipelineResult(success=True, record=cleaned)


def _fail(ctx: _StepContext, step: ProcessingStep, error: BaseException) -> PipelineResult:
    ctx.session.rollback()
    message = f"{step.value}: {error}"
    file_repo.update_status(
        ctx.session, ctx.file_id, FileStatus.failed, error_message=message
    )
    log_repo.write(
        ctx.session,
        LogEntry(
            file_id=ctx.file_id,
            enrichment_run_id=ctx.enrichment_run_id,
            step=step,
            level=ProcessingLogLevel.error,
            message=message,
        ),
    )
    ctx.session.commit()
    return PipelineResult(success=False, errors=[message])


def _record_to_scalars(record: BookRecord) -> MetadataScalars:
    return MetadataScalars(
        title=record.title,
        subtitle=record.subtitle,
        language=record.language,
        series=record.series,
        series_index=record.series_index,
        series_total=record.series_total,
        publisher=record.publisher,
        isbn13=record.isbn13,
        isbn10=record.isbn10,
        asin=record.asin,
        published=record.published,
        year=record.year,
        confidence=Decimal(str(record.confidence)) if record.confidence is not None else None,
    )


def _record_to_data(record: BookRecord) -> dict[str, Any]:
    return _jsonify(asdict(record))


def _jsonify(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonify(v) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value
