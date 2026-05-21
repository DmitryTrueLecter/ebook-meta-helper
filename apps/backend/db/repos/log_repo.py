"""Repository for the processing_logs table — per-step pipeline log entries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.processing_log import (
    ProcessingLog,
    ProcessingLogLevel,
    ProcessingStep,
)


@dataclass(frozen=True)
class LogEntry:
    """One pipeline-step log record. `step` and `level` are mandatory."""

    file_id: int
    step: ProcessingStep
    level: ProcessingLogLevel = ProcessingLogLevel.info
    message: Optional[str] = None
    enrichment_run_id: Optional[int] = None
    details: Optional[dict[str, Any]] = None
    duration_ms: Optional[int] = None


def write(session: Session, entry: LogEntry) -> ProcessingLog:
    record = ProcessingLog(
        file_id=entry.file_id,
        enrichment_run_id=entry.enrichment_run_id,
        step=entry.step,
        level=entry.level,
        message=entry.message,
        details=entry.details,
        duration_ms=entry.duration_ms,
    )
    session.add(record)
    session.flush()
    return record


def get_for_file(
    session: Session, file_id: int, limit: int = 50
) -> list[ProcessingLog]:
    return list(
        session.execute(
            select(ProcessingLog)
            .where(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.created_at.desc(), ProcessingLog.id.desc())
            .limit(limit)
        ).scalars()
    )
