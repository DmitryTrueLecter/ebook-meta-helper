"""Unit tests for app.api.routes.ai_calls — TestClient with dependency overrides."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.api.routes import ai_calls as routes
from db.models.ai_call import AICallOrigin, AICallTier


def _make_call(
    id_: int = 1,
    file_id: int = 7,
    enrichment_run_id=None,
    config_version_id=None,
    is_canonical: bool = True,
):
    return SimpleNamespace(
        id=id_,
        file_id=file_id,
        enrichment_run_id=enrichment_run_id,
        config_version_id=config_version_id,
        origin=AICallOrigin.pipeline,
        sequence=1,
        tier=AICallTier.cheap,
        is_canonical=is_canonical,
        model="gpt-4o-mini",
        effort=None,
        response_format_ref="book.v1",
        system_prompt="You are a librarian.",
        user_prompt="Extract metadata.",
        raw_response='{"title": "Foundation"}',
        prompt_tokens=120,
        completion_tokens=40,
        cost_usd=Decimal("0.001234"),
        duration_ms=850,
        confidence=Decimal("0.910"),
        parse_errors=None,
        created_at=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def client():
    fake_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    with TestClient(app) as test_client:
        yield test_client, fake_session
    app.dependency_overrides.clear()


class TestListFileAICalls:
    """GET /api/files/{file_id}/ai-calls — summary rows without prompt/response text."""

    def test_returns_summaries_and_passes_file_id(self, client, monkeypatch):
        test_client, _ = client
        captured = {}

        def capture(_s, file_id):
            captured["file_id"] = file_id
            return [_make_call(1), _make_call(2, is_canonical=False)]

        monkeypatch.setattr(routes.ai_call_repo, "get_for_file", capture)

        response = test_client.get("/api/files/7/ai-calls")
        assert response.status_code == 200
        body = response.json()
        assert captured["file_id"] == 7
        assert [item["id"] for item in body] == [1, 2]
        assert body[0]["cost_usd"] == 0.001234
        assert body[0]["confidence"] == 0.91
        assert body[0]["tier"] == "cheap"

    def test_summary_omits_big_text_fields(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(
            routes.ai_call_repo, "get_for_file", lambda _s, _id: [_make_call()]
        )
        response = test_client.get("/api/files/7/ai-calls")
        assert response.status_code == 200
        item = response.json()[0]
        for field in ("system_prompt", "user_prompt", "raw_response", "parse_errors"):
            assert field not in item

    def test_empty_list_when_no_calls(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.ai_call_repo, "get_for_file", lambda _s, _id: [])
        response = test_client.get("/api/files/7/ai-calls")
        assert response.status_code == 200
        assert response.json() == []


class TestGetAICallDetail:
    """GET /api/ai-calls/{call_id} — full call including prompts and provenance."""

    def test_returns_detail_with_text_and_provenance(self, client, monkeypatch):
        test_client, _ = client
        call = _make_call(id_=5, enrichment_run_id=3, config_version_id=2)
        monkeypatch.setattr(routes.ai_call_repo, "get_by_id", lambda _s, _id: call)

        response = test_client.get("/api/ai-calls/5")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == 5
        assert body["system_prompt"] == "You are a librarian."
        assert body["raw_response"] == '{"title": "Foundation"}'
        assert body["origin"] == "pipeline"
        assert body["config_version_id"] == 2
        assert body["enrichment_run_id"] == 3

    def test_404_when_call_missing(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.ai_call_repo, "get_by_id", lambda _s, _id: None)
        response = test_client.get("/api/ai-calls/999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
