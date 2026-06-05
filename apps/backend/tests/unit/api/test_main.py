"""Unit tests for app.api.main — router wiring, removed placeholder, SPA fallback."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import FRONTEND_DIR, app


@pytest.fixture
def client():
    fake_session = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestRouterWiring:
    """All three API routers (directories, files, scan) and /api/health are mounted; placeholder is gone."""

    def test_health_endpoint_responds(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_directories_router_is_registered(self):
        prefixes = {getattr(r, "path", "") for r in app.routes}
        assert any(path.startswith("/api/directories") for path in prefixes)

    def test_files_router_is_registered(self):
        prefixes = {getattr(r, "path", "") for r in app.routes}
        assert any(path.startswith("/api/files") for path in prefixes)

    def test_scan_router_is_registered(self):
        prefixes = {getattr(r, "path", "") for r in app.routes}
        assert any(path.startswith("/api/scan") for path in prefixes)

    def test_books_placeholder_is_removed(self):
        api_paths = {
            getattr(r, "path", "") for r in app.routes if hasattr(r, "path")
        }
        assert "/api/books" not in api_paths


class TestFrontendDirPath:
    """FRONTEND_DIR always ends in frontend/dist; its anchor adapts to the layout.

    DMI-75 replaced the hardcoded apps/frontend/dist path with _resolve_frontend_dir(),
    which picks an existing candidate (container vs dev tree) or falls back to
    parents[2]/frontend/dist when nothing is built — so the grandparent dir is not
    guaranteed to be "apps". FRONTEND_DIST_DIR overrides the search entirely. See DMI-111.
    """

    def test_frontend_dir_ends_in_frontend_dist(self):
        assert FRONTEND_DIR.name == "dist"
        assert FRONTEND_DIR.parent.name == "frontend"

    def test_env_override_takes_precedence(self, monkeypatch, tmp_path):
        from app.api.main import _resolve_frontend_dir

        override = tmp_path / "custom" / "dist"
        monkeypatch.setenv("FRONTEND_DIST_DIR", str(override))
        assert _resolve_frontend_dir() == override


class TestSpaFallback:
    """SPA fallback serves index.html for non-API paths and does not shadow API routes."""

    @pytest.mark.skipif(
        not FRONTEND_DIR.exists(),
        reason="frontend/dist not built in this environment",
    )
    def test_spa_fallback_returns_index_html_for_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "<!doctype" in response.text.lower() or "<html" in response.text.lower()

    @pytest.mark.skipif(
        not FRONTEND_DIR.exists(),
        reason="frontend/dist not built in this environment",
    )
    def test_spa_fallback_returns_index_html_for_arbitrary_route(self, client):
        response = client.get("/directories/123")
        assert response.status_code == 200
        # Same index.html bytes regardless of path.
        assert "<!doctype" in response.text.lower() or "<html" in response.text.lower()

    @pytest.mark.skipif(
        not FRONTEND_DIR.exists(),
        reason="frontend/dist not built in this environment",
    )
    def test_api_health_not_shadowed_by_spa_fallback(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.skipif(
        not (FRONTEND_DIR / "assets").exists(),
        reason="frontend/dist/assets not built in this environment",
    )
    def test_assets_mount_does_not_collide_with_spa_fallback(self, client):
        # The /assets mount precedes the SPA catchall — a missing asset 404s instead of
        # falling through to index.html.
        response = client.get("/assets/definitely-not-an-asset-xyz.js")
        assert response.status_code == 404
