"""Repository for the scan_jobs table — live scan progress for the UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from db.models.scan_job import ScanJob, ScanJobStatus


@dataclass(frozen=True)
class ScanProgress:
    """Partial update payload — only set fields are written."""

    files_discovered: Optional[int] = None
    files_processed: Optional[int] = None
    current_file_id: Optional[int] = None


def create(
    session: Session,
    root_path: str,
    root_directory_id: Optional[int] = None,
) -> ScanJob:
    job = ScanJob(
        root_path=root_path,
        root_directory_id=root_directory_id,
        status=ScanJobStatus.pending,
    )
    session.add(job)
    session.flush()
    return job


def start(session: Session, job_id: int) -> ScanJob:
    job = _load(session, job_id)
    if job.status != ScanJobStatus.pending:
        raise ValueError(
            f"ScanJob {job_id} cannot be started from status={job.status.value}"
        )
    job.status = ScanJobStatus.running
    job.started_at = datetime.now()
    session.flush()
    return job


def update_progress(
    session: Session, job_id: int, progress: ScanProgress
) -> ScanJob:
    job = _load(session, job_id)
    if progress.files_discovered is not None:
        job.files_discovered = progress.files_discovered
    if progress.files_processed is not None:
        job.files_processed = progress.files_processed
    if progress.current_file_id is not None:
        job.current_file_id = progress.current_file_id
    session.flush()
    return job


def finish(session: Session, job_id: int) -> ScanJob:
    job = _load(session, job_id)
    job.status = ScanJobStatus.done
    job.finished_at = datetime.now()
    session.flush()
    return job


def fail(session: Session, job_id: int, error_message: str) -> ScanJob:
    job = _load(session, job_id)
    job.status = ScanJobStatus.failed
    job.error_message = error_message
    job.finished_at = datetime.now()
    session.flush()
    return job


def get_active(session: Session) -> Optional[ScanJob]:
    """Return the running scan job (most recently started wins if several)."""
    return session.execute(
        select(ScanJob)
        .where(ScanJob.status == ScanJobStatus.running)
        .order_by(ScanJob.started_at.desc(), ScanJob.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def find_active_or_pending(session: Session) -> Optional[ScanJob]:
    """Most recent running or pending job — running always wins, ties broken by newest created_at then id."""
    status_priority = case(
        (ScanJob.status == ScanJobStatus.running, 0),
        else_=1,
    )
    return session.execute(
        select(ScanJob)
        .where(ScanJob.status.in_([ScanJobStatus.running, ScanJobStatus.pending]))
        .order_by(status_priority, ScanJob.created_at.desc(), ScanJob.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def find_latest_completed(session: Session) -> Optional[ScanJob]:
    """Most recently finished job (done / failed / cancelled), newest by finished_at."""
    terminal_statuses = [
        ScanJobStatus.done,
        ScanJobStatus.failed,
        ScanJobStatus.cancelled,
    ]
    return session.execute(
        select(ScanJob)
        .where(ScanJob.status.in_(terminal_statuses))
        .order_by(ScanJob.finished_at.desc(), ScanJob.id.desc())
        .limit(1)
    ).scalar_one_or_none()


def _load(session: Session, job_id: int) -> ScanJob:
    job = session.get(ScanJob, job_id)
    if job is None:
        raise LookupError(f"ScanJob {job_id} not found")
    return job
