"""Pipeline steps: read embedded metadata (discover) and AI-only analyze (explicit per-file)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.ai.base import AIConfigSnapshot
from app.ai.enrich import enrich
from app.metadata.cleaner import clean_record
from app.metadata.reader.registry import read_metadata
from app.models.book import BookRecord
from app.models.pipeline import PipelineResult
from db.models.ai_call import AICallOrigin
from db.models.file_record import FileStatus
from db.models.metadata import MetadataSource
from db.models.processing_log import ProcessingLogLevel, ProcessingStep
from db.repos import ai_call_repo, file_repo, log_repo, metadata_repo
from db.repos.ai_call_repo import AICallInput
from db.repos.log_repo import LogEntry
from db.repos.metadata_repo import MetadataInput, MetadataScalars


@dataclass(frozen=True)
class _StepContext:
    file_id: int
    enrichment_run_id: Optional[int]
    session: Session


@dataclass(frozen=True)
class AnalyzeRequest:
    """Everything analyze_file needs for one AI-only enrich: call identity, session, and active config."""

    record: BookRecord
    file_id: int
    enrichment_run_id: int
    session: Session
    config: AIConfigSnapshot
    config_version_id: Optional[int]


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


def analyze_file(request: AnalyzeRequest) -> PipelineResult:
    """AI-only enrich of an already-read file — drives reading→enriched/failed and persists the call chain."""
    ctx = _StepContext(
        file_id=request.file_id,
        enrichment_run_id=request.enrichment_run_id,
        session=request.session,
    )
    file_repo.update_status(ctx.session, ctx.file_id, FileStatus.enriching)
    ctx.session.commit()  # release the lock before the network call

    try:
        provider_name = os.environ.get("AI_PROVIDER")
        if not provider_name:
            raise RuntimeError("AI_PROVIDER is not set")
        outcome = enrich(
            request.record,
            provider_name=provider_name,
            config=request.config,
            directory_hint=None,
        )
        cleaned = clean_record(outcome.record)
    except Exception as exc:
        return _fail(ctx, ProcessingStep.ai_enrich, exc)

    try:
        ai_call_repo.record_calls(
            ctx.session,
            AICallInput(
                file_id=ctx.file_id,
                enrichment_run_id=ctx.enrichment_run_id,
                config_version_id=request.config_version_id,
                origin=AICallOrigin.pipeline,
            ),
            outcome,
        )
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
