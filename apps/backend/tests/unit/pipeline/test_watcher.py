"""Unit tests for app.pipeline.watcher — outer loop, env validation, crash-recovery reset."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.pipeline import watcher
from app.pipeline.scan_cycle import CycleResult
from db.base import Base
import db.models  # noqa: F401 — register all models with Base.metadata
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def in_memory_db(monkeypatch):
    """Swap db.session and watcher.get_session for an in-memory SQLite engine."""
    from contextlib import contextmanager

    from db import session as db_session

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Maker = sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)

    @contextmanager
    def fake_get_session():
        s = Maker()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(db_session, "engine", engine)
    monkeypatch.setattr(db_session, "SessionLocal", Maker)
    monkeypatch.setattr(watcher, "get_session", fake_get_session)

    yield engine, Maker
    Base.metadata.drop_all(engine)
    engine.dispose()


class TestStartupRecovery:
    def test_resets_in_flight_statuses_to_pending(self, in_memory_db):
        engine, Maker = in_memory_db

        with Maker() as session:
            directory = Directory(path="/lib", name="lib", depth=0)
            session.add(directory)
            session.flush()
            session.add_all([
                FileRecord(directory_id=directory.id, filename="a.fb2", status=FileStatus.reading),
                FileRecord(directory_id=directory.id, filename="b.fb2", status=FileStatus.ai_queued),
                FileRecord(directory_id=directory.id, filename="c.fb2", status=FileStatus.enriching),
                FileRecord(directory_id=directory.id, filename="d.fb2", status=FileStatus.enriched),
                FileRecord(directory_id=directory.id, filename="e.fb2", status=FileStatus.pending),
                FileRecord(directory_id=directory.id, filename="f.fb2", status=FileStatus.failed),
            ])
            session.commit()

        reset_count = watcher._reset_stalled_on_startup()
        assert reset_count == 3

        with Maker() as session:
            by_name = {f.filename: f for f in session.query(FileRecord).all()}
            assert by_name["a.fb2"].status == FileStatus.pending
            assert by_name["b.fb2"].status == FileStatus.pending
            assert by_name["c.fb2"].status == FileStatus.pending
            # untouched
            assert by_name["d.fb2"].status == FileStatus.enriched
            assert by_name["e.fb2"].status == FileStatus.pending
            assert by_name["f.fb2"].status == FileStatus.failed

    def test_resets_clear_prior_error_message(self, in_memory_db):
        engine, Maker = in_memory_db

        with Maker() as session:
            directory = Directory(path="/lib", name="lib", depth=0)
            session.add(directory)
            session.flush()
            session.add(
                FileRecord(
                    directory_id=directory.id,
                    filename="stuck.fb2",
                    status=FileStatus.enriching,
                    error_message="will be cleared",
                )
            )
            session.commit()

        watcher._reset_stalled_on_startup()

        with Maker() as session:
            record = session.query(FileRecord).filter_by(filename="stuck.fb2").one()
            assert record.status == FileStatus.pending
            assert record.error_message is None

    def test_returns_zero_when_no_stalled_rows(self, in_memory_db):
        assert watcher._reset_stalled_on_startup() == 0


class TestEnvValidation:
    def test_missing_new_books_dir_raises(self, monkeypatch):
        monkeypatch.delenv("NEW_BOOKS_DIR", raising=False)

        # load_dotenv may pick up a file in dev — patch it to a no-op
        with patch("app.pipeline.watcher.load_dotenv", return_value=None):
            with pytest.raises(RuntimeError, match="NEW_BOOKS_DIR is not set"):
                watcher.run_watcher()


class TestLoopBody:
    def test_single_tick_calls_run_scan_cycle_then_sleeps(self, monkeypatch, in_memory_db):
        monkeypatch.setenv("NEW_BOOKS_DIR", "/tmp/fake-books")
        monkeypatch.setenv("WATCH_SLEEP_SECONDS", "0")

        cycle_calls: list[str] = []

        def fake_cycle(root):
            cycle_calls.append(root)
            if len(cycle_calls) >= 2:
                # break out of the infinite loop after two ticks
                raise KeyboardInterrupt
            return CycleResult(
                scan_job_id=1, files_discovered=0, files_processed=0, files_failed=0
            )

        with patch("app.pipeline.watcher.load_dotenv", return_value=None), patch(
            "app.pipeline.watcher.run_scan_cycle", side_effect=fake_cycle
        ), patch("app.pipeline.watcher.time.sleep", return_value=None):
            with pytest.raises(KeyboardInterrupt):
                watcher.run_watcher()

        assert cycle_calls == ["/tmp/fake-books", "/tmp/fake-books"]

    def test_cycle_exception_does_not_break_loop(self, monkeypatch, in_memory_db):
        monkeypatch.setenv("NEW_BOOKS_DIR", "/tmp/fake-books")
        monkeypatch.setenv("WATCH_SLEEP_SECONDS", "0")

        attempts: list[int] = []

        def flaky_cycle(root):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("transient DB connection error")
            raise KeyboardInterrupt

        with patch("app.pipeline.watcher.load_dotenv", return_value=None), patch(
            "app.pipeline.watcher.run_scan_cycle", side_effect=flaky_cycle
        ), patch("app.pipeline.watcher.time.sleep", return_value=None):
            with pytest.raises(KeyboardInterrupt):
                watcher.run_watcher()

        assert len(attempts) == 2  # second tick proves loop survived the first error
