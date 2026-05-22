"""Integration test fixtures: real MariaDB, alembic-upgraded schema, per-test truncate."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.base import Base
import db.models  # noqa: F401 — register all models with Base.metadata


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _resolve_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")


@pytest.fixture(scope="session")
def database_url() -> str:
    url = _resolve_database_url()
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL / DATABASE_URL not set — skipping repository integration tests"
        )
    return url


@pytest.fixture(scope="session")
def engine(database_url: str) -> Generator[Engine, None, None]:
    eng = create_engine(database_url, future=True)
    _run_alembic(database_url, "upgrade", "head")
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session, None, None]:
    _truncate_all_tables(engine)
    with Session(engine) as s:
        yield s


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


# Order matters only for documentation; FOREIGN_KEY_CHECKS=0 lets us truncate freely.
_TABLES_TO_TRUNCATE = (
    "processing_logs",
    "metadata",
    "scan_jobs",
    "enrichment_runs",
    "directory_hints",
    "file_records",
    "directories",
)


def _truncate_all_tables(engine: Engine) -> None:
    """Reset row data and AUTO_INCREMENT counters for every domain table."""
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in _TABLES_TO_TRUNCATE:
            conn.execute(text(f"TRUNCATE TABLE {table}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
