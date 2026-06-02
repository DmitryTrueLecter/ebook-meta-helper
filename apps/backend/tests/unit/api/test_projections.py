"""Unit tests for app.api.projections.to_scan_status."""

from __future__ import annotations

from types import SimpleNamespace

from app.api.projections import to_scan_status
from db.models.scan_job import ScanJobStatus


def _job(status_value, error_message=None, current_file=None):
    return SimpleNamespace(
        id=1,
        status=status_value,
        files_discovered=5,
        files_processed=2,
        current_file=current_file,
        error_message=error_message,
    )


def test_failed_job_projects_error_message():
    job = _job(ScanJobStatus.failed, error_message="scanner crashed: ENOENT /lib")
    result = to_scan_status(job)
    assert result.status == "failed"
    assert result.error_message == "scanner crashed: ENOENT /lib"


def test_running_job_projects_null_error_message():
    result = to_scan_status(_job(ScanJobStatus.running))
    assert result.status == "running"
    assert result.error_message is None


def test_done_job_projects_null_error_message():
    result = to_scan_status(_job(ScanJobStatus.done))
    assert result.status == "done"
    assert result.error_message is None


def test_current_filename_projected_from_current_file():
    current_file = SimpleNamespace(filename="in_progress.fb2")
    result = to_scan_status(_job(ScanJobStatus.running, current_file=current_file))
    assert result.current_filename == "in_progress.fb2"
