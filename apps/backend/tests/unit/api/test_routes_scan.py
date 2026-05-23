"""Unit tests for app.api.routes.scan — TestClient with dependency overrides."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.api.routes import scan as routes
from db.models.scan_job import ScanJobStatus


def _make_job(
    id_: int = 1,
    status_value: ScanJobStatus = ScanJobStatus.running,
    files_discovered: int = 0,
    files_processed: int = 0,
    current_file=None,
):
    return SimpleNamespace(
        id=id_,
        status=status_value,
        files_discovered=files_discovered,
        files_processed=files_processed,
        current_file=current_file,
    )


@pytest.fixture
def client():
    fake_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    with TestClient(app) as test_client:
        yield test_client, fake_session
    app.dependency_overrides.clear()


class TestGetScanStatus:
    """GET /api/scan/status returns the active (running/pending) job, or the latest completed one."""

    def test_returns_running_job_with_current_filename(self, client, monkeypatch):
        test_client, _ = client
        current_file = SimpleNamespace(id=42, filename="being_processed.epub")
        job = _make_job(
            id_=7,
            status_value=ScanJobStatus.running,
            files_discovered=20,
            files_processed=5,
            current_file=current_file,
        )
        monkeypatch.setattr(routes.scan_job_repo, "find_active_or_pending", lambda _s: job)
        latest_called = {"count": 0}

        def fake_latest(_s):
            latest_called["count"] += 1
            return None

        monkeypatch.setattr(routes.scan_job_repo, "find_latest_completed", fake_latest)

        response = test_client.get("/api/scan/status")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 7
        assert body["status"] == "running"
        assert body["files_discovered"] == 20
        assert body["files_processed"] == 5
        assert body["current_filename"] == "being_processed.epub"
        # Fallback is not consulted when an active/pending job exists.
        assert latest_called["count"] == 0

    def test_returns_pending_job_when_no_running_one(self, client, monkeypatch):
        test_client, _ = client
        job = _make_job(
            id_=3,
            status_value=ScanJobStatus.pending,
            files_discovered=0,
            files_processed=0,
            current_file=None,
        )
        monkeypatch.setattr(routes.scan_job_repo, "find_active_or_pending", lambda _s: job)
        monkeypatch.setattr(routes.scan_job_repo, "find_latest_completed", lambda _s: None)

        response = test_client.get("/api/scan/status")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 3
        assert body["status"] == "pending"
        assert body["current_filename"] is None

    def test_falls_back_to_latest_completed_when_no_active(self, client, monkeypatch):
        test_client, _ = client
        completed = _make_job(
            id_=99,
            status_value=ScanJobStatus.done,
            files_discovered=120,
            files_processed=120,
            current_file=None,
        )
        monkeypatch.setattr(routes.scan_job_repo, "find_active_or_pending", lambda _s: None)
        monkeypatch.setattr(routes.scan_job_repo, "find_latest_completed", lambda _s: completed)

        response = test_client.get("/api/scan/status")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 99
        assert body["status"] == "done"
        assert body["files_processed"] == 120

    def test_falls_back_to_latest_failed_job(self, client, monkeypatch):
        test_client, _ = client
        failed = _make_job(
            id_=50,
            status_value=ScanJobStatus.failed,
            files_discovered=10,
            files_processed=3,
            current_file=None,
        )
        monkeypatch.setattr(routes.scan_job_repo, "find_active_or_pending", lambda _s: None)
        monkeypatch.setattr(routes.scan_job_repo, "find_latest_completed", lambda _s: failed)

        response = test_client.get("/api/scan/status")
        assert response.status_code == 200
        assert response.json()["status"] == "failed"

    def test_returns_null_when_no_jobs_exist(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.scan_job_repo, "find_active_or_pending", lambda _s: None)
        monkeypatch.setattr(routes.scan_job_repo, "find_latest_completed", lambda _s: None)

        response = test_client.get("/api/scan/status")
        assert response.status_code == 200
        assert response.json() is None

    def test_current_filename_is_null_when_current_file_unset(self, client, monkeypatch):
        test_client, _ = client
        job = _make_job(
            id_=2,
            status_value=ScanJobStatus.running,
            current_file=None,
        )
        monkeypatch.setattr(routes.scan_job_repo, "find_active_or_pending", lambda _s: job)
        monkeypatch.setattr(routes.scan_job_repo, "find_latest_completed", lambda _s: None)

        response = test_client.get("/api/scan/status")
        assert response.status_code == 200
        assert response.json()["current_filename"] is None
