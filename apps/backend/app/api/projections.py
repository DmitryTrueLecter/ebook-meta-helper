"""ORM → Pydantic projections shared across API routers."""

from __future__ import annotations

from app.api.schemas import ScanJobProgress
from db.models.scan_job import ScanJob


def to_scan_status(job: ScanJob) -> ScanJobProgress:
    current_filename = job.current_file.filename if job.current_file is not None else None
    return ScanJobProgress(
        id=job.id,
        status=job.status.value,
        files_discovered=job.files_discovered,
        files_processed=job.files_processed,
        current_filename=current_filename,
        error_message=job.error_message,
    )
