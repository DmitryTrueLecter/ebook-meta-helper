"""Scan API: progress-polling endpoint for the in-flight or latest completed scan."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import ScanJobStatus
from db.models.scan_job import ScanJob
from db.repos import scan_job_repo

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.get("/status", response_model=Optional[ScanJobStatus])
def get_scan_status(db: Session = Depends(get_db)) -> Optional[ScanJobStatus]:
    """Return the active (running/pending) scan job, falling back to the most recent completed one.

    Frontend polls this every 2s during an active scan. Returns `null` when no job exists yet.
    """
    job = scan_job_repo.find_active_or_pending(db)
    if job is None:
        job = scan_job_repo.find_latest_completed(db)
    if job is None:
        return None
    return _to_scan_status(job)


def _to_scan_status(job: ScanJob) -> ScanJobStatus:
    current_filename = job.current_file.filename if job.current_file is not None else None
    return ScanJobStatus(
        id=job.id,
        status=job.status.value,
        files_discovered=job.files_discovered,
        files_processed=job.files_processed,
        current_filename=current_filename,
    )
