"""Integration tests for migration 008 — real MariaDB, real alembic 007↔008.

Real ENUM ALTER + data remap can only be exercised against MariaDB, not SQLite.
"""

from __future__ import annotations

import os
import subprocess
import sys
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
    """Roll the schema back to 007 so the test exercises the real 007→008 upgrade.

    Restores the DB to head afterwards so the session-scoped suite state is intact.
    """
    eng = create_engine(database_url, future=True)
    _run_alembic(database_url, "downgrade", "007")
    try:
        yield eng
    finally:
        _run_alembic(database_url, "upgrade", "head")
        eng.dispose()


def _truncate(eng: Engine) -> None:
    with eng.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text("TRUNCATE TABLE enrichment_runs"))
        conn.execute(text("TRUNCATE TABLE file_records"))
        conn.execute(text("TRUNCATE TABLE directories"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


def _enum_values(eng: Engine, table: str, column: str) -> set[str]:
    with eng.connect() as conn:
        column_type = conn.execute(
            text(
                "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"t": table, "c": column},
        ).scalar_one()
    inner = column_type[column_type.index("(") + 1 : column_type.rindex(")")]
    return {token.strip().strip("'") for token in inner.split(",")}


class TestMigration008:
    def test_legacy_ai_queued_rows_remap_and_enums_widen(self, migration_engine):
        eng = migration_engine
        _truncate(eng)
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO directories (path, name, depth, file_count, discovered_at) "
                    "VALUES ('/legacy', 'legacy', 0, 0, NOW())"
                )
            )
            dir_id = conn.execute(
                text("SELECT id FROM directories WHERE path = '/legacy'")
            ).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO file_records (directory_id, filename, status, discovered_at, updated_at) "
                    "VALUES (:d, 'stuck.fb2', 'ai_queued', NOW(), NOW()), "
                    "(:d, 'done.fb2', 'enriched', NOW(), NOW())"
                ),
                {"d": dir_id},
            )
            conn.execute(
                text(
                    "INSERT INTO enrichment_runs (directory_id, `trigger`, status, file_count, "
                    "success_count, failure_count, started_at) "
                    "VALUES (:d, 'user_directory', 'done', 1, 1, 0, NOW()), "
                    "(:d, 'scan', 'done', 1, 1, 0, NOW())"
                ),
                {"d": dir_id},
            )

        _run_alembic(str(eng.url.render_as_string(hide_password=False)), "upgrade", "head")

        assert {"read", "analyze_queued", "missing"} <= _enum_values(
            eng, "file_records", "status"
        )
        assert _enum_values(eng, "enrichment_runs", "trigger") == {
            "scan",
            "user_file",
            "retry",
        }
        assert _enum_values(eng, "directories", "status") == {"active", "missing"}

        with eng.connect() as conn:
            statuses = dict(
                conn.execute(text("SELECT filename, status FROM file_records")).all()
            )
            triggers = [
                row[0]
                for row in conn.execute(text("SELECT `trigger` FROM enrichment_runs")).all()
            ]
            dir_statuses = [
                row[0] for row in conn.execute(text("SELECT status FROM directories")).all()
            ]

        assert statuses["stuck.fb2"] == "analyze_queued"
        assert statuses["done.fb2"] == "enriched"
        assert "user_directory" not in triggers
        assert sorted(triggers) == ["scan", "user_file"]
        assert dir_statuses == ["active"]

    def test_run_migrations_boot_path_is_idempotent(self, migration_engine):
        """RUN_MIGRATIONS=1 prod boot runs `upgrade head`; re-running it is a no-op."""
        eng = migration_engine
        _truncate(eng)
        url = str(eng.url.render_as_string(hide_password=False))

        _run_alembic(url, "upgrade", "head")
        _run_alembic(url, "upgrade", "head")

        with eng.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert version == "008"
