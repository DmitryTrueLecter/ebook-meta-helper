"""Unit tests for db.repos.scan_job_repo — lifecycle and active-job query."""

from __future__ import annotations

import pytest

from db.models.scan_job import ScanJobStatus
from db.repos import scan_job_repo
from db.repos.scan_job_repo import ScanProgress


class TestCreate:
    def test_starts_pending(self, session):
        job = scan_job_repo.create(session, root_path="/data/new_books")
        assert job.id is not None
        assert job.status == ScanJobStatus.pending
        assert job.root_path == "/data/new_books"
        assert job.files_discovered == 0
        assert job.files_processed == 0
        assert job.started_at is None
        assert job.finished_at is None


class TestStart:
    def test_pending_to_running(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        started = scan_job_repo.start(session, job.id)
        assert started.status == ScanJobStatus.running
        assert started.started_at is not None

    def test_start_twice_rejected(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        scan_job_repo.start(session, job.id)
        with pytest.raises(ValueError):
            scan_job_repo.start(session, job.id)

    def test_raises_on_missing(self, session):
        with pytest.raises(LookupError):
            scan_job_repo.start(session, job_id=999)


class TestUpdateProgress:
    def test_partial_update(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        scan_job_repo.start(session, job.id)
        updated = scan_job_repo.update_progress(
            session, job.id, ScanProgress(files_discovered=10)
        )
        assert updated.files_discovered == 10
        assert updated.files_processed == 0

        updated = scan_job_repo.update_progress(
            session, job.id, ScanProgress(files_processed=5)
        )
        assert updated.files_discovered == 10
        assert updated.files_processed == 5

    def test_full_update(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        scan_job_repo.start(session, job.id)
        updated = scan_job_repo.update_progress(
            session,
            job.id,
            ScanProgress(files_discovered=100, files_processed=42, current_file_id=None),
        )
        assert updated.files_discovered == 100
        assert updated.files_processed == 42


class TestFinishAndFail:
    def test_finish_marks_done(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        scan_job_repo.start(session, job.id)
        done = scan_job_repo.finish(session, job.id)
        assert done.status == ScanJobStatus.done
        assert done.finished_at is not None

    def test_fail_sets_error_and_finished(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        scan_job_repo.start(session, job.id)
        failed = scan_job_repo.fail(session, job.id, error_message="permission denied")
        assert failed.status == ScanJobStatus.failed
        assert failed.error_message == "permission denied"
        assert failed.finished_at is not None


class TestGetActive:
    def test_returns_running_job(self, session):
        scan_job_repo.create(session, root_path="/d1")  # pending — not active
        job2 = scan_job_repo.create(session, root_path="/d2")
        scan_job_repo.start(session, job2.id)

        active = scan_job_repo.get_active(session)
        assert active is not None
        assert active.id == job2.id

    def test_returns_none_when_idle(self, session):
        scan_job_repo.create(session, root_path="/d")  # pending only
        assert scan_job_repo.get_active(session) is None

    def test_done_jobs_not_active(self, session):
        job = scan_job_repo.create(session, root_path="/d")
        scan_job_repo.start(session, job.id)
        scan_job_repo.finish(session, job.id)
        assert scan_job_repo.get_active(session) is None
