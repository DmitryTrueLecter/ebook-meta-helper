"""Migration boundary for 010 (schema) + 011 (v1 seed) against real MariaDB (DMI-144).

LONGTEXT / ENUM / DATETIME(fsp) DDL and the FK-supporting-index downgrade quirk only surface
on MariaDB, not SQLite.
"""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _run_alembic(database_url: str, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def migration_engine(database_url: str) -> Generator[Engine, None, None]:
    """Roll the schema back to 009 so the test drives the real 009→010→011 upgrade.

    Restores the DB to head afterwards so the session-scoped suite state is intact.
    """
    eng = create_engine(database_url, future=True)
    _run_alembic(database_url, "downgrade", "009")
    try:
        yield eng
    finally:
        _run_alembic(database_url, "upgrade", "head")
        eng.dispose()


def _table_exists(eng: Engine, table: str) -> bool:
    with eng.connect() as conn:
        return (
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t"
                ),
                {"t": table},
            ).scalar()
            == 1
        )


def _column_exists(eng: Engine, table: str, column: str) -> bool:
    with eng.connect() as conn:
        return (
            conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
                ),
                {"t": table, "c": column},
            ).scalar()
            == 1
        )


class TestMigration010And011:
    def test_upgrade_creates_tables_and_seeds_single_active_v1(self, migration_engine):
        eng = migration_engine
        url = str(eng.url.render_as_string(hide_password=False))

        _run_alembic(url, "upgrade", "head")

        assert _table_exists(eng, "ai_calls")
        assert _table_exists(eng, "ai_config_versions")
        assert _column_exists(eng, "enrichment_runs", "config_version_id")

        with eng.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT version, cheap_model, expensive_model, effort, "
                    "escalation_threshold, provider, response_format_ref, is_active "
                    "FROM ai_config_versions WHERE is_active = 1"
                )
            ).all()
            total = conn.execute(
                text("SELECT COUNT(*) FROM ai_config_versions")
            ).scalar()

        assert total == 1
        assert len(rows) == 1
        seeded = rows[0]
        assert seeded.version == 1
        assert seeded.cheap_model == "gpt-4o-mini"
        assert seeded.expensive_model == "gpt-4o-mini"
        assert seeded.effort == "high"
        assert Decimal(str(seeded.escalation_threshold)) == Decimal("0.700")
        assert seeded.provider == "openai"
        assert seeded.response_format_ref == "book_metadata.v2"
        assert seeded.is_active == 1

    def test_seeded_system_prompt_matches_build_system_prompt(self, migration_engine):
        from app.ai.prompt.book_metadata import build_system_prompt

        eng = migration_engine
        url = str(eng.url.render_as_string(hide_password=False))
        _run_alembic(url, "upgrade", "head")

        with eng.connect() as conn:
            stored = conn.execute(
                text("SELECT system_prompt FROM ai_config_versions WHERE version = 1")
            ).scalar_one()
        assert stored == build_system_prompt()

    def test_downgrade_round_trip_removes_tables_and_column(self, migration_engine):
        eng = migration_engine
        url = str(eng.url.render_as_string(hide_password=False))

        _run_alembic(url, "upgrade", "head")
        _run_alembic(url, "downgrade", "009")

        assert not _table_exists(eng, "ai_calls")
        assert not _table_exists(eng, "ai_config_versions")
        assert not _column_exists(eng, "enrichment_runs", "config_version_id")

        # Re-upgrade proves the round-trip is repeatable (and restores head for the fixture).
        _run_alembic(url, "upgrade", "head")
        assert _table_exists(eng, "ai_calls")
        assert _column_exists(eng, "enrichment_runs", "config_version_id")
