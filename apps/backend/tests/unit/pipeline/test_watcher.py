"""Unit tests for app.pipeline.watcher — outer loop, env validation, crash-recovery reset, job consumption."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from app.models.book import BookRecord
from app.pipeline import scan_cycle, watcher
from app.pipeline.scan_cycle import CycleResult
from db.base import Base
import db.models  # noqa: F401 — register all models with Base.metadata
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from db.models.scan_job import ScanJob, ScanJobStatus
from db.repos import scan_job_repo

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
    def test_resets_in_flight_statuses_to_analyze_queued(self, in_memory_db):
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
                # durable queue marker survives a restart untouched
                FileRecord(directory_id=directory.id, filename="g.fb2", status=FileStatus.analyze_queued),
            ])
            session.commit()

        reset_count = watcher._reset_stalled_on_startup()
        assert reset_count == 3

        with Maker() as session:
            by_name = {f.filename: f for f in session.query(FileRecord).all()}
            assert by_name["a.fb2"].status == FileStatus.analyze_queued
            assert by_name["b.fb2"].status == FileStatus.analyze_queued
            assert by_name["c.fb2"].status == FileStatus.analyze_queued
            # untouched
            assert by_name["d.fb2"].status == FileStatus.enriched
            assert by_name["e.fb2"].status == FileStatus.pending
            assert by_name["f.fb2"].status == FileStatus.failed
            assert by_name["g.fb2"].status == FileStatus.analyze_queued

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
            assert record.status == FileStatus.analyze_queued
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

        def fake_cycle(job_id, root):
            cycle_calls.append(root)
            if len(cycle_calls) >= 2:
                # break out of the infinite loop after two ticks
                raise KeyboardInterrupt
            return CycleResult(
                scan_job_id=job_id, files_discovered=0, files_processed=0, files_failed=0
            )

        with patch("app.pipeline.watcher.load_dotenv", return_value=None), patch(
            "app.pipeline.watcher.run_scan_cycle", side_effect=fake_cycle
        ), patch("app.pipeline.watcher.time.sleep", return_value=None):
            with pytest.raises(KeyboardInterrupt):
                watcher.run_watcher()

        # No pending job exists, so each idle tick enqueues + claims a NEW_BOOKS_DIR sweep job.
        assert cycle_calls == ["/tmp/fake-books", "/tmp/fake-books"]

    def test_cycle_exception_does_not_break_loop(self, monkeypatch, in_memory_db):
        monkeypatch.setenv("NEW_BOOKS_DIR", "/tmp/fake-books")
        monkeypatch.setenv("WATCH_SLEEP_SECONDS", "0")

        attempts: list[int] = []

        def flaky_cycle(job_id, root):
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


@pytest.fixture
def shared_db(monkeypatch):
    """Shared-cache in-memory DB wired into both watcher and scan_cycle session factories."""
    from db import session as db_session

    engine = create_engine(
        "sqlite:///file::memory:?cache=shared&uri=true",
        future=True,
        connect_args={"uri": True},
    )
    Base.metadata.create_all(engine)
    Maker = sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)

    @contextmanager
    def factory():
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
    monkeypatch.setattr(watcher, "get_session", factory)
    monkeypatch.setattr(scan_cycle, "get_session", factory)

    yield engine, Maker, factory
    Base.metadata.drop_all(engine)
    engine.dispose()


def _make_book_tree(tmp_path):
    root = tmp_path / "library"
    (root / "sci-fi").mkdir(parents=True)
    (root / "sci-fi" / "book.fb2").write_bytes(b"<?xml version='1.0'?><FictionBook/>")
    return root


def _stub_provider():
    provider = MagicMock()
    provider.summarize_directory.return_value = {
        "series_name": "S",
        "universe": None,
        "genre": "scifi",
        "tags": [],
        "language": "en",
        "confidence": 0.5,
        "notes": None,
    }
    return provider


class TestPendingJobConsumption:
    def test_pending_job_picked_up_and_run_to_done_on_same_id(
        self, tmp_path, shared_db, monkeypatch
    ):
        engine, Maker, factory = shared_db
        root = _make_book_tree(tmp_path)
        monkeypatch.setenv("AI_PROVIDER", "fake")

        # API-style: a pending job already exists for this root_path.
        with Maker() as s:
            job = scan_job_repo.create(s, root_path=str(root))
            s.commit()
            job_id = job.id

        observed_status_during: list = []

        def _spy_enrich(record, provider_name, directory_hint=None):
            with Maker() as s:
                active = scan_job_repo.find_active_or_pending(s)
                observed_status_during.append((active.id, active.status))
            record.source = "ai"
            return record

        with patch("app.pipeline.scan_cycle.get_provider", return_value=_stub_provider()), patch(
            "app.pipeline.process_file.read_metadata", side_effect=lambda r: r
        ), patch("app.pipeline.process_file.enrich", side_effect=_spy_enrich):
            watcher._run_one_iteration(str(root))

        # Same job id ran while in running state, observable via find_active_or_pending.
        assert observed_status_during == [(job_id, ScanJobStatus.running)]

        with Maker() as s:
            final = s.get(ScanJob, job.id)
            assert final.id == job_id
            assert final.status == ScanJobStatus.done
            assert final.started_at is not None
            assert final.finished_at is not None
            assert final.files_discovered == 1
            assert final.files_processed == 1
            # no second job was created — the API's job is the one that ran
            assert s.query(ScanJob).count() == 1

    def test_failing_job_marked_failed_on_same_id(self, tmp_path, shared_db, monkeypatch):
        engine, Maker, factory = shared_db
        root = _make_book_tree(tmp_path)
        monkeypatch.setenv("AI_PROVIDER", "fake")

        with Maker() as s:
            job = scan_job_repo.create(s, root_path=str(root))
            s.commit()
            job_id = job.id

        provider = MagicMock()
        provider.summarize_directory.side_effect = RuntimeError("OpenAI outage")

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), patch(
            "app.pipeline.process_file.read_metadata", side_effect=lambda r: r
        ):
            # the loop swallows it; call the iteration directly to assert the raise path
            with pytest.raises(RuntimeError, match="OpenAI outage"):
                watcher._run_one_iteration(str(root))

        with Maker() as s:
            final = s.get(ScanJob, job_id)
            assert final.status == ScanJobStatus.failed
            assert "OpenAI outage" in final.error_message
            assert s.query(ScanJob).count() == 1

    def test_idle_iteration_enqueues_new_books_sweep_job(self, shared_db, monkeypatch):
        engine, Maker, factory = shared_db
        monkeypatch.setenv("AI_PROVIDER", "fake")

        captured_root: list = []

        def fake_cycle(job_id, root):
            captured_root.append((job_id, root))
            return CycleResult(
                scan_job_id=job_id, files_discovered=0, files_processed=0, files_failed=0
            )

        with patch("app.pipeline.watcher.run_scan_cycle", side_effect=fake_cycle):
            watcher._run_one_iteration("/new-books")

        # No pending job existed, so a NEW_BOOKS_DIR sweep job was created, claimed, and run.
        assert len(captured_root) == 1
        job_id, root = captured_root[0]
        assert root == "/new-books"
        with Maker() as s:
            job = s.get(ScanJob, job_id)
            assert job.root_path == "/new-books"
            assert job.status == ScanJobStatus.running
