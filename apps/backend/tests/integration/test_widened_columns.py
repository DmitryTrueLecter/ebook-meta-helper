"""Widened isbn10/isbn13 + processing_logs.message — real MariaDB (SQLite ignores column length, so the bug is invisible there)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.pipeline.scan_cycle import run_scan_cycle
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import ProcessingStep
from db.repos import log_repo, metadata_repo, scan_job_repo
from db.repos.log_repo import LogEntry
from db.repos.metadata_repo import MetadataInput, MetadataScalars


BACKEND_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
SEPARATOR_ISBN_FIXTURE = ASSETS_DIR / "fb2" / "separator_isbn.fb2"

SEPARATOR_ISBN13 = "978-0-306-40615-7"


def _make_directory_and_file(session: Session) -> FileRecord:
    directory = Directory(path="/lib/widen", name="widen", depth=0)
    session.add(directory)
    session.flush()
    file_record = FileRecord(directory_id=directory.id, filename="book.fb2")
    session.add(file_record)
    session.flush()
    return file_record


class TestWidenedColumnsPersist:
    def test_separator_bearing_isbn_persists(self, session):
        """A real ISBN with separators (17 chars) exceeds the old CHAR(13) and must now fit."""
        file_record = _make_directory_and_file(session)

        metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.file,
                data={"raw": True},
                scalars=MetadataScalars(isbn13=SEPARATOR_ISBN13),
            ),
        )
        session.commit()

        stored = session.execute(
            select(Metadata).where(Metadata.file_id == file_record.id)
        ).scalar_one()
        assert stored.isbn13 == SEPARATOR_ISBN13

    def test_oversized_log_message_persists(self, session):
        """The wrapped DataError + SQL text exceeds String(1024); Text must hold it."""
        file_record = _make_directory_and_file(session)
        long_message = "x" * 5000

        log_repo.write(
            session,
            LogEntry(
                file_id=file_record.id,
                step=ProcessingStep.read_metadata,
                message=long_message,
            ),
        )
        session.commit()

        stored_message = session.execute(
            text("SELECT message FROM processing_logs WHERE file_id = :fid"),
            {"fid": file_record.id},
        ).scalar_one()
        assert stored_message == long_message


class TestDiscoverWithSeparatorIsbnCommits:
    @pytest.fixture
    def session_factory(self, engine: Engine):
        Maker = sessionmaker(
            engine, autocommit=False, autoflush=False, expire_on_commit=False
        )

        @contextmanager
        def factory() -> Generator[Session, None, None]:
            s = Maker()
            try:
                yield s
                s.commit()
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        return factory

    def test_discover_over_separator_isbn_file_commits_tree(
        self, tmp_path, session, session_factory
    ):
        """Discover must NOT abort the cycle on the separator-ISBN file — the tree commits."""
        library = tmp_path / "library"
        target_dir = library / "sci-fi"
        target_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(SEPARATOR_ISBN_FIXTURE, target_dir / "book.fb2")

        with session_factory() as s:
            scan_job_repo.create(s, root_path=str(library.resolve()))
            s.flush()
            job_id = scan_job_repo.claim_next_pending(s).id
        result = run_scan_cycle(
            job_id, str(library.resolve()), session_factory=session_factory
        )

        # Cycle completed, file read (not aborted/rolled back).
        assert result.files_read == 1
        assert result.files_failed == 0

        record = session.execute(select(FileRecord)).scalar_one()
        assert record.status == FileStatus.read

        # Directory rows for the scanned tree are committed.
        dir_paths = set(session.execute(select(Directory.path)).scalars())
        assert str(target_dir.resolve()) in dir_paths

        # The separator-bearing ISBN was stored intact (no truncation/mangling).
        snapshot = session.execute(
            select(Metadata).where(
                Metadata.file_id == record.id,
                Metadata.source == MetadataSource.file,
            )
        ).scalar_one()
        assert snapshot.isbn13 == SEPARATOR_ISBN13


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


def _column_type(eng: Engine, table: str, column: str) -> str:
    with eng.connect() as conn:
        return conn.execute(
            text(
                "SELECT COLUMN_TYPE FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c"
            ),
            {"t": table, "c": column},
        ).scalar_one()


class TestMigration009RoundTrips:
    """Real ALTER COLUMN can only be exercised against MariaDB, not SQLite."""

    @pytest.fixture
    def migration_engine(self, database_url: str) -> Generator[Engine, None, None]:
        eng = create_engine(database_url, future=True)
        # Downgrade to CHAR(13) would reject any leftover wide ISBN; start clean.
        with eng.begin() as conn:
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
            conn.execute(text("TRUNCATE TABLE processing_logs"))
            conn.execute(text("TRUNCATE TABLE metadata"))
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        _run_alembic(database_url, "downgrade", "008")
        try:
            yield eng
        finally:
            _run_alembic(database_url, "upgrade", "head")
            eng.dispose()

    def test_upgrade_widens_and_downgrade_restores(self, migration_engine):
        eng = migration_engine
        url = str(eng.url.render_as_string(hide_password=False))

        # At 008: narrow columns.
        assert _column_type(eng, "metadata", "isbn10").startswith("char(10)")
        assert _column_type(eng, "metadata", "isbn13").startswith("char(13)")
        assert _column_type(eng, "processing_logs", "message").startswith("varchar(1024)")

        _run_alembic(url, "upgrade", "head")
        assert _column_type(eng, "metadata", "isbn10").startswith("varchar(20)")
        assert _column_type(eng, "metadata", "isbn13").startswith("varchar(20)")
        assert _column_type(eng, "processing_logs", "message") == "text"

        _run_alembic(url, "downgrade", "008")
        assert _column_type(eng, "metadata", "isbn10").startswith("char(10)")
        assert _column_type(eng, "metadata", "isbn13").startswith("char(13)")
        assert _column_type(eng, "processing_logs", "message").startswith("varchar(1024)")
