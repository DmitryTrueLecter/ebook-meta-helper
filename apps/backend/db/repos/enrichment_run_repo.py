"""Repository for the enrichment_runs table — open via create, close via finish/fail."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from db.models.enrichment_run import (
    EnrichmentRun,
    EnrichmentStatus,
    EnrichmentTrigger,
)


@dataclass(frozen=True)
class EnrichmentRunInput:
    """Open-a-run payload — directory binding, trigger, and AI provenance."""

    directory_id: Optional[int]
    trigger: EnrichmentTrigger
    ai_model: Optional[str] = None
    prompt_version: Optional[str] = None


@dataclass(frozen=True)
class EnrichmentRunResult:
    """Close-a-run payload — success/failure counters and optional cost."""

    success_count: int
    failure_count: int
    cost_usd: Optional[Decimal] = None


def create(session: Session, spec: EnrichmentRunInput) -> EnrichmentRun:
    run = EnrichmentRun(
        directory_id=spec.directory_id,
        trigger=spec.trigger,
        ai_model=spec.ai_model,
        prompt_version=spec.prompt_version,
        status=EnrichmentStatus.running,
    )
    session.add(run)
    session.flush()
    return run


def finish(
    session: Session, run_id: int, outcome: EnrichmentRunResult
) -> EnrichmentRun:
    run = _load_open_run(session, run_id)
    run.status = EnrichmentStatus.done
    run.success_count = outcome.success_count
    run.failure_count = outcome.failure_count
    run.cost_usd = outcome.cost_usd
    run.finished_at = datetime.now()
    session.flush()
    return run


def fail(session: Session, run_id: int, error_message: str) -> EnrichmentRun:
    run = _load_open_run(session, run_id)
    run.status = EnrichmentStatus.failed
    run.error_message = error_message
    run.finished_at = datetime.now()
    session.flush()
    return run


def _load_open_run(session: Session, run_id: int) -> EnrichmentRun:
    run = session.get(EnrichmentRun, run_id)
    if run is None:
        raise LookupError(f"EnrichmentRun {run_id} not found")
    if run.status != EnrichmentStatus.running:
        raise ValueError(
            f"EnrichmentRun {run_id} is already closed (status={run.status.value})"
        )
    return run
