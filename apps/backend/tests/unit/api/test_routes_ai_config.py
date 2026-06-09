"""Unit tests for app.api.routes.ai_config — TestClient with dependency overrides."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.api.routes import ai_config as routes


def _make_version(id_: int = 1, version: int = 1, is_active: bool = True):
    return SimpleNamespace(
        id=id_,
        version=version,
        label="initial",
        system_prompt="You are a librarian.",
        cheap_model="gpt-4o-mini",
        expensive_model="gpt-4o",
        effort="medium",
        escalation_threshold=Decimal("0.700"),
        provider="openai",
        response_format_ref="book.v1",
        is_active=is_active,
        created_at=datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc),
        created_by="seed",
    )


@pytest.fixture
def client():
    fake_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    with TestClient(app) as test_client:
        yield test_client, fake_session
    app.dependency_overrides.clear()


class TestGetActiveAIConfig:
    """GET /api/ai-config/active — the single active version."""

    def test_returns_active_version(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.ai_config_repo, "get_active", lambda _s: _make_version())
        response = test_client.get("/api/ai-config/active")
        assert response.status_code == 200
        body = response.json()
        assert body["is_active"] is True
        assert body["escalation_threshold"] == 0.7
        assert body["effort"] == "medium"

    def test_404_when_no_active_version(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.ai_config_repo, "get_active", lambda _s: None)
        response = test_client.get("/api/ai-config/active")
        assert response.status_code == 404
        assert "No active AI config version" in response.json()["detail"]


class TestListAIConfigVersions:
    """GET /api/ai-config/versions — every version."""

    def test_returns_all_versions(self, client, monkeypatch):
        test_client, _ = client
        versions = [_make_version(2, 2, is_active=True), _make_version(1, 1, is_active=False)]
        monkeypatch.setattr(routes.ai_config_repo, "list_versions", lambda _s: versions)
        response = test_client.get("/api/ai-config/versions")
        assert response.status_code == 200
        body = response.json()
        assert [item["version"] for item in body] == [2, 1]
        assert body[0]["is_active"] is True
        assert body[1]["is_active"] is False

    def test_empty_list_when_none(self, client, monkeypatch):
        test_client, _ = client
        monkeypatch.setattr(routes.ai_config_repo, "list_versions", lambda _s: [])
        response = test_client.get("/api/ai-config/versions")
        assert response.status_code == 200
        assert response.json() == []
