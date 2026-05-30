"""Unit tests for app.api.routes.directories — TestClient with dependency overrides."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.api.routes import directories as routes
from db.models.file_record import FileStatus
from db.models.scan_job import ScanJobStatus as ScanJobState
from db.repos.directory_repo import DirectoryStats


def _make_directory(id_: int, name: str, path: str, depth: int, parent_id=None, children=None):
    """Build a Directory-shaped stub good enough for from_attributes projection."""
    return SimpleNamespace(
        id=id_, name=name, path=path, depth=depth,
        parent_id=parent_id, children=children or [],
    )


def _make_file(id_: int, filename: str, status_value: FileStatus, extension="epub", format_="EPUB", sort_order=None):
    return SimpleNamespace(
        id=id_, filename=filename, status=status_value,
        extension=extension, format=format_, sort_order=sort_order,
    )


@pytest.fixture
def client():
    fake_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    with TestClient(app) as test_client:
        yield test_client, fake_session
    app.dependency_overrides.clear()


class TestListDirectoryTree:
    """GET /api/directories returns nested tree with per-directory counts."""

    def test_returns_only_roots_with_nested_children(self, client, monkeypatch):
        test_client, _ = client
        child = _make_directory(2, "child", "/lib/child", 1, parent_id=1)
        root = _make_directory(1, "root", "/lib", 0, parent_id=None, children=[child])
        orphan = _make_directory(3, "orphan", "/other", 0, parent_id=None, children=[])

        monkeypatch.setattr(routes.directory_repo, "get_tree", lambda _s: [root, child, orphan])
        monkeypatch.setattr(
            routes.directory_repo, "get_status_counts",
            lambda _s: {
                1: DirectoryStats(file_count=10, pending_count=3, enriched_count=5, accepted_count=2),
                2: DirectoryStats(file_count=4, pending_count=1, enriched_count=2, accepted_count=1),
                3: DirectoryStats(file_count=0, pending_count=0, enriched_count=0, accepted_count=0),
            },
        )

        response = test_client.get("/api/directories")
        assert response.status_code == 200
        body = response.json()
        assert [node["id"] for node in body] == [1, 3]
        assert body[0]["children"][0]["id"] == 2
        assert body[0]["pending_count"] == 3
        assert body[0]["children"][0]["accepted_count"] == 1

    def test_directory_without_files_yields_zero_counts(self, client, monkeypatch):
        test_client, _ = client
        root = _make_directory(1, "root", "/lib", 0, parent_id=None, children=[])

        monkeypatch.setattr(routes.directory_repo, "get_tree", lambda _s: [root])
        monkeypatch.setattr(routes.directory_repo, "get_status_counts", lambda _s: {})

        response = test_client.get("/api/directories")
        assert response.status_code == 200
        node = response.json()[0]
        assert node["file_count"] == 0
        assert node["pending_count"] == 0
        assert node["enriched_count"] == 0
        assert node["accepted_count"] == 0

    def test_empty_tree_returns_empty_list(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.directory_repo, "get_tree", lambda _s: [])
        monkeypatch.setattr(routes.directory_repo, "get_status_counts", lambda _s: {})

        response = test_client.get("/api/directories")
        assert response.status_code == 200
        assert response.json() == []


class TestGetDirectoryDetail:
    """GET /api/directories/{id} returns directory + file list, optional ?status filter."""

    def test_returns_directory_with_files(self, client, monkeypatch):
        test_client, _ = client
        directory = _make_directory(1, "lib", "/lib", 0)
        files = [
            _make_file(10, "a.epub", FileStatus.pending),
            _make_file(11, "b.epub", FileStatus.enriched, sort_order=2.5),
        ]
        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(
            routes.directory_repo, "get_stats_for_directory",
            lambda _s, _id: DirectoryStats(2, 1, 1, 0),
        )
        monkeypatch.setattr(routes.file_repo, "get_by_directory", lambda _s, _d, _st: files)
        monkeypatch.setattr(
            routes.metadata_repo, "find_files_with_ai_suggestion",
            lambda _s, ids: {11},
        )

        response = test_client.get("/api/directories/1")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert body["file_count"] == 2
        assert len(body["files"]) == 2
        assert body["files"][0]["has_ai_suggestion"] is False
        assert body["files"][1]["has_ai_suggestion"] is True
        assert body["files"][1]["sort_order"] == 2.5

    def test_status_filter_is_passed_to_repo(self, client, monkeypatch):
        test_client, _ = client
        directory = _make_directory(1, "lib", "/lib", 0)
        captured = {}

        def capture(_s, _d, status_arg):
            captured["status"] = status_arg
            return []

        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(routes.directory_repo, "get_stats_for_directory", lambda _s, _id: DirectoryStats(0, 0, 0, 0))
        monkeypatch.setattr(routes.file_repo, "get_by_directory", capture)
        monkeypatch.setattr(routes.metadata_repo, "find_files_with_ai_suggestion", lambda _s, ids: set())

        response = test_client.get("/api/directories/1?status=enriched")
        assert response.status_code == 200
        assert captured["status"] == FileStatus.enriched

    def test_no_status_filter_passes_none(self, client, monkeypatch):
        test_client, _ = client
        directory = _make_directory(1, "lib", "/lib", 0)
        captured = {}

        def capture(_s, _d, status_arg):
            captured["status"] = status_arg
            return []

        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(routes.directory_repo, "get_stats_for_directory", lambda _s, _id: DirectoryStats(0, 0, 0, 0))
        monkeypatch.setattr(routes.file_repo, "get_by_directory", capture)
        monkeypatch.setattr(routes.metadata_repo, "find_files_with_ai_suggestion", lambda _s, ids: set())

        response = test_client.get("/api/directories/1")
        assert response.status_code == 200
        assert captured["status"] is None

    def test_empty_status_filter_treated_as_no_filter(self, client, monkeypatch):
        test_client, _ = client
        directory = _make_directory(1, "lib", "/lib", 0)
        captured = {}

        def capture(_s, _d, status_arg):
            captured["status"] = status_arg
            return []

        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(routes.directory_repo, "get_stats_for_directory", lambda _s, _id: DirectoryStats(0, 0, 0, 0))
        monkeypatch.setattr(routes.file_repo, "get_by_directory", capture)
        monkeypatch.setattr(routes.metadata_repo, "find_files_with_ai_suggestion", lambda _s, ids: set())

        response = test_client.get("/api/directories/1?status=")
        assert response.status_code == 200
        assert captured["status"] is None

    def test_invalid_status_filter_returns_400(self, client, monkeypatch):
        test_client, _ = client
        directory = _make_directory(1, "lib", "/lib", 0)
        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(routes.directory_repo, "get_status_counts", lambda _s: {})

        response = test_client.get("/api/directories/1?status=nonsense")
        assert response.status_code == 400
        assert "nonsense" in response.json()["detail"]

    def test_unknown_directory_returns_404(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: None)

        response = test_client.get("/api/directories/999")
        assert response.status_code == 404
        assert "999" in response.json()["detail"]


class TestTriggerDirectoryScan:
    """POST /api/directories/{id}/scan creates a pending ScanJob and returns 202."""

    def test_creates_pending_job_and_returns_202(self, client, monkeypatch):
        test_client, fake_session = client
        directory = _make_directory(1, "lib", "/lib", 0)
        created_job = SimpleNamespace(
            id=42, status=ScanJobState.pending,
            files_discovered=0, files_processed=0,
        )
        captured = {}

        def fake_create(_s, root_path, root_directory_id):
            captured["root_path"] = root_path
            captured["root_directory_id"] = root_directory_id
            return created_job

        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(routes.scan_job_repo, "get_active", lambda _s: None)
        monkeypatch.setattr(routes.scan_job_repo, "create", fake_create)

        response = test_client.post("/api/directories/1/scan")
        assert response.status_code == 202
        body = response.json()
        assert body["id"] == 42
        assert body["status"] == "pending"
        assert body["files_discovered"] == 0
        assert body["current_filename"] is None
        assert captured == {"root_path": "/lib", "root_directory_id": 1}
        fake_session.commit.assert_called_once()

    def test_running_job_returns_409(self, client, monkeypatch):
        test_client, _ = client
        directory = _make_directory(1, "lib", "/lib", 0)
        running = SimpleNamespace(id=7, status=ScanJobState.running)

        create_called = {"count": 0}

        def fake_create(*_args, **_kwargs):
            create_called["count"] += 1
            return SimpleNamespace(id=99, status=ScanJobState.pending, files_discovered=0, files_processed=0)

        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: directory)
        monkeypatch.setattr(routes.scan_job_repo, "get_active", lambda _s: running)
        monkeypatch.setattr(routes.scan_job_repo, "create", fake_create)

        response = test_client.post("/api/directories/1/scan")
        assert response.status_code == 409
        assert "7" in response.json()["detail"]
        assert create_called["count"] == 0

    def test_unknown_directory_returns_404(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.directory_repo, "get_by_id", lambda _s, _id: None)

        response = test_client.post("/api/directories/999/scan")
        assert response.status_code == 404
