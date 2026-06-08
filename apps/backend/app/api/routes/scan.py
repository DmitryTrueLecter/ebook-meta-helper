"""Scan API: progress-polling endpoint for the in-flight or latest completed scan."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.projections import to_scan_status
from app.api.schemas import ScanJobProgress
from db.repos import scan_job_repo

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.get("/status", response_model=Optional[ScanJobProgress])
def get_scan_status(db: Session = Depends(get_db)) -> Optional[ScanJobProgress]:
    """Return the active (running/pending) scan job, falling back to the most recent completed one.

    Frontend polls this every 2s during an active scan. Returns `null` when no job exists yet.
    """
    job = scan_job_repo.find_active_or_pending(db)
    if job is None:
        job = scan_job_repo.find_latest_completed(db)
    if job is None:
        return None
    return to_scan_status(job)
