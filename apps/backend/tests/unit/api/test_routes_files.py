"""Unit tests for app.api.routes.files — TestClient with dependency overrides."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.api.routes import files as routes
from db.models.file_record import FileStatus
from db.models.metadata import MetadataSource
from db.models.processing_log import ProcessingLogLevel, ProcessingStep
from db.repos.file_repo import InvalidStatusTransition, PaginatedRecords


def _make_file(
    id_: int = 1,
    filename: str = "book.epub",
    status_value: FileStatus = FileStatus.enriched,
    extension: str = "epub",
    format_: str = "EPUB",
    sort_order=None,
    directory_id: int = 1,
    error_message=None,
):
    directory = SimpleNamespace(id=directory_id, path="/library/sci-fi", name="sci-fi")
    return SimpleNamespace(
        id=id_,
        filename=filename,
        status=status_value,
        extension=extension,
        format=format_,
        sort_order=sort_order,
        directory_id=directory_id,
        directory=directory,
        error_message=error_message,
    )


def _make_metadata(
    id_: int = 10,
    source: MetadataSource = MetadataSource.ai,
    title: str = "Foundation",
    is_current: bool = True,
    enrichment_run_id=None,
    data=None,
):
    return SimpleNamespace(
        id=id_,
        source=source,
        is_current=is_current,
        title=title,
        subtitle=None,
        language="en",
        series="Foundation",
        series_index=1,
        series_total=None,
        publisher=None,
        isbn13="9780553293357",
        isbn10=None,
        asin=None,
        published=None,
        year=None,
        confidence=Decimal("0.92"),
        data=data or {"authors": ["Isaac Asimov"], "tags": ["sci-fi"]},
        created_at=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        enrichment_run_id=enrichment_run_id,
    )


def _make_log(step=ProcessingStep.ai_enrich, message="enriched", duration_ms=1500):
    return SimpleNamespace(
        step=step,
        level=ProcessingLogLevel.info,
        message=message,
        duration_ms=duration_ms,
        created_at=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def client():
    fake_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    with TestClient(app) as test_client:
        yield test_client, fake_session
    app.dependency_overrides.clear()


class TestListFiles:
    """GET /api/files — paginated listing."""

    def test_returns_paginated_payload_with_total(self, client, monkeypatch):
        test_client, _ = client
        files_ = [_make_file(1, "a.epub"), _make_file(2, "b.epub", FileStatus.pending)]
        monkeypatch.setattr(
            routes.file_repo, "list_paginated",
            lambda _s, page, page_size, directory_id, status: PaginatedRecords(
                items=files_, total=12
            ),
        )
        monkeypatch.setattr(
            routes.metadata_repo, "find_files_with_ai_suggestion",
            lambda _s, ids: {1},
        )

        response = test_client.get("/api/files")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 12
        assert body["page"] == 1
        assert body["page_size"] == 50
        assert [item["id"] for item in body["items"]] == [1, 2]
        assert body["items"][0]["has_ai_suggestion"] is True
        assert body["items"][1]["has_ai_suggestion"] is False

    def test_passes_directory_status_page_and_page_size_to_repo(self, client, monkeypatch):
        test_client, _ = client
        captured = {}

        def capture(_s, page, page_size, directory_id, status):
            captured.update(page=page, page_size=page_size, directory_id=directory_id, status=status)
            return PaginatedRecords(items=[], total=0)

        monkeypatch.setattr(routes.file_repo, "list_paginated", capture)
        monkeypatch.setattr(routes.metadata_repo, "find_files_with_ai_suggestion", lambda _s, ids: set())

        response = test_client.get(
            "/api/files?directory_id=7&status=enriched&page=3&page_size=25"
        )
        assert response.status_code == 200
        assert captured == {"page": 3, "page_size": 25, "directory_id": 7, "status": FileStatus.enriched}

    def test_invalid_status_filter_returns_400(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(
            routes.file_repo, "list_paginated",
            lambda *a, **kw: PaginatedRecords(items=[], total=0),
        )
        response = test_client.get("/api/files?status=not_a_status")
        assert response.status_code == 400
        assert "Invalid status filter" in response.json()["detail"]

    def test_page_size_above_cap_returns_422(self, client):
        test_client, _ = client
        response = test_client.get("/api/files?page_size=999")
        assert response.status_code == 422

    def test_page_below_one_returns_422(self, client):
        test_client, _ = client
        response = test_client.get("/api/files?page=0")
        assert response.status_code == 422


class TestGetFileDetail:
    """GET /api/files/{id} — current file+ai snapshots."""

    def test_returns_file_with_both_snapshots(self, client, monkeypatch):
        test_client, _ = client
        record = _make_file()
        file_snap = _make_metadata(id_=1, source=MetadataSource.file, title="File Title")
        ai_snap = _make_metadata(id_=2, source=MetadataSource.ai, title="AI Title")

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: record)

        def fake_get_current(_s, _file_id, source):
            return {MetadataSource.file: file_snap, MetadataSource.ai: ai_snap}[source]

        monkeypatch.setattr(routes.metadata_repo, "get_current", fake_get_current)

        response = test_client.get("/api/files/1")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 1
        assert body["file_metadata"]["title"] == "File Title"
        assert body["ai_metadata"]["title"] == "AI Title"

    def test_returns_null_snapshots_when_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file())
        monkeypatch.setattr(routes.metadata_repo, "get_current", lambda _s, _f, _src: None)

        response = test_client.get("/api/files/1")
        assert response.status_code == 200
        body = response.json()
        assert body["file_metadata"] is None
        assert body["ai_metadata"] is None

    def test_404_when_file_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: None)

        response = test_client.get("/api/files/999")
        assert response.status_code == 404


class TestListFileMetadata:
    """GET /api/files/{id}/metadata — full history."""

    def test_returns_history_newest_first(self, client, monkeypatch):
        test_client, _ = client
        history = [
            _make_metadata(id_=3, source=MetadataSource.ai),
            _make_metadata(id_=2, source=MetadataSource.file, title="Older"),
            _make_metadata(id_=1, source=MetadataSource.ai, title="Oldest", is_current=False),
        ]
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file())
        monkeypatch.setattr(routes.metadata_repo, "get_history", lambda _s, _id: history)

        response = test_client.get("/api/files/1/metadata")
        assert response.status_code == 200
        body = response.json()
        assert [item["id"] for item in body] == [3, 2, 1]
        assert body[2]["is_current"] is False

    def test_404_when_file_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: None)
        response = test_client.get("/api/files/999/metadata")
        assert response.status_code == 404


class TestListFileLogs:
    """GET /api/files/{id}/logs — last N processing logs."""

    def test_returns_logs_with_default_limit_50(self, client, monkeypatch):
        test_client, _ = client
        logs = [_make_log(step=ProcessingStep.ai_enrich), _make_log(step=ProcessingStep.read_metadata)]
        captured = {}

        def capture(_s, file_id, limit):
            captured["limit"] = limit
            return logs

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file())
        monkeypatch.setattr(routes.log_repo, "get_for_file", capture)

        response = test_client.get("/api/files/1/logs")
        assert response.status_code == 200
        body = response.json()
        assert captured["limit"] == 50
        assert len(body) == 2
        assert body[0]["step"] == "ai_enrich"

    def test_custom_limit_passed_through(self, client, monkeypatch):
        test_client, _ = client
        captured = {}

        def capture(_s, file_id, limit):
            captured["limit"] = limit
            return []

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file())
        monkeypatch.setattr(routes.log_repo, "get_for_file", capture)

        response = test_client.get("/api/files/1/logs?limit=10")
        assert response.status_code == 200
        assert captured["limit"] == 10

    def test_404_when_file_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: None)
        response = test_client.get("/api/files/999/logs")
        assert response.status_code == 404


class TestAccept:
    """POST /api/files/{id}/accept — invokes accept_file service."""

    def test_returns_updated_list_item_on_success(self, client, monkeypatch):
        test_client, session = client
        record_before = _make_file(status_value=FileStatus.enriched)
        record_after = _make_file(status_value=FileStatus.accepted)
        get_by_id_calls = iter([record_before, record_after])

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: next(get_by_id_calls))
        monkeypatch.setattr(routes, "accept_file", lambda _s, _id: None)

        response = test_client.post("/api/files/1/accept")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "accepted"
        assert body["has_ai_suggestion"] is True
        session.commit.assert_called_once()

    def test_404_when_file_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: None)
        response = test_client.post("/api/files/999/accept")
        assert response.status_code == 404

    def test_409_when_accept_service_raises(self, client, monkeypatch):
        test_client, session = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file())

        def boom(_s, _id):
            raise routes.AcceptError("no AI metadata to accept")

        monkeypatch.setattr(routes, "accept_file", boom)

        response = test_client.post("/api/files/1/accept")
        assert response.status_code == 409
        assert "no AI metadata" in response.json()["detail"]
        session.commit.assert_not_called()

    def test_409_on_invalid_status_transition(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file())

        def boom(_s, _id):
            raise InvalidStatusTransition(FileStatus.pending, FileStatus.accepted)

        monkeypatch.setattr(routes, "accept_file", boom)

        response = test_client.post("/api/files/1/accept")
        assert response.status_code == 409


class TestReject:
    """POST /api/files/{id}/reject — sets status to rejected; does not touch disk."""

    def test_updates_status_to_rejected(self, client, monkeypatch):
        test_client, session = client
        record = _make_file(status_value=FileStatus.enriched)
        rejected = _make_file(status_value=FileStatus.rejected)
        captured = {}

        def fake_update(_s, file_id, new_status):
            captured["status"] = new_status
            return rejected

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: record)
        monkeypatch.setattr(routes.file_repo, "update_status", fake_update)
        monkeypatch.setattr(routes.metadata_repo, "find_files_with_ai_suggestion", lambda _s, ids: {1})

        response = test_client.post("/api/files/1/reject")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "rejected"
        assert captured["status"] == FileStatus.rejected
        session.commit.assert_called_once()

    def test_409_on_invalid_status_transition(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file(status_value=FileStatus.pending))

        def boom(_s, _id, _ns):
            raise InvalidStatusTransition(FileStatus.pending, FileStatus.rejected)

        monkeypatch.setattr(routes.file_repo, "update_status", boom)

        response = test_client.post("/api/files/1/reject")
        assert response.status_code == 409

    def test_404_when_file_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: None)
        response = test_client.post("/api/files/999/reject")
        assert response.status_code == 404


class TestEnrich:
    """POST /api/files/{id}/enrich — queues a new EnrichmentRun and returns 202."""

    def test_returns_202_with_run_id_and_queues_status(self, client, monkeypatch):
        test_client, session = client
        record_before = _make_file(status_value=FileStatus.enriched)
        record_after = _make_file(status_value=FileStatus.ai_queued)
        run = SimpleNamespace(id=42)

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: record_before)
        monkeypatch.setattr(routes.file_repo, "update_status", lambda _s, _id, _ns: record_after)
        monkeypatch.setattr(routes.enrichment_run_repo, "create", lambda _s, _spec: run)

        response = test_client.post("/api/files/1/enrich")
        assert response.status_code == 202
        body = response.json()
        assert body["enrichment_run_id"] == 42
        assert body["file_id"] == 1
        assert body["status"] == "ai_queued"
        session.commit.assert_called_once()

    def test_409_on_invalid_status_transition(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: _make_file(status_value=FileStatus.reading))

        def boom(_s, _id, _ns):
            raise InvalidStatusTransition(FileStatus.reading, FileStatus.ai_queued)

        monkeypatch.setattr(routes.file_repo, "update_status", boom)

        response = test_client.post("/api/files/1/enrich")
        assert response.status_code == 409

    def test_404_when_file_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: None)
        response = test_client.post("/api/files/999/enrich")
        assert response.status_code == 404

    def test_enrichment_run_uses_user_file_trigger_and_directory_id(self, client, monkeypatch):
        test_client, _ = client
        record = _make_file(directory_id=7, status_value=FileStatus.enriched)
        captured = {}

        def capture(_s, spec):
            captured["spec"] = spec
            return SimpleNamespace(id=1)

        monkeypatch.setattr(routes.file_repo, "get_by_id", lambda _s, _id: record)
        monkeypatch.setattr(
            routes.file_repo, "update_status",
            lambda _s, _id, _ns: _make_file(status_value=FileStatus.ai_queued),
        )
        monkeypatch.setattr(routes.enrichment_run_repo, "create", capture)

        response = test_client.post("/api/files/1/enrich")
        assert response.status_code == 202
        from db.models.enrichment_run import EnrichmentTrigger as Trigger
        assert captured["spec"].trigger == Trigger.user_file
        assert captured["spec"].directory_id == 7
