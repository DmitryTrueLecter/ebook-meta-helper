"""Unit tests for app.pipeline.scan_cycle — DB-driven scan cycle."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.book import BookRecord
from app.models.pipeline import PipelineResult
from app.pipeline.scan_cycle import run_scan_cycle
from db.base import Base
import db.models  # noqa: F401 — register all models with Base.metadata
from db.models.directory import Directory
from db.models.directory_hint import DirectoryHint
from db.models.enrichment_run import EnrichmentRun, EnrichmentStatus
from db.models.file_record import FileRecord, FileStatus
from db.models.scan_job import ScanJob, ScanJobStatus
from db.repos import scan_job_repo


def _running_job(session_factory, root: str) -> int:
    """Create and claim a running ScanJob — the state the watcher hands to run_scan_cycle."""
    with session_factory() as session:
        scan_job_repo.create(session, root_path=root)
        session.flush()
        job = scan_job_repo.claim_next_pending(session)
        return job.id


@pytest.fixture
def shared_engine():
    """One in-memory engine shared by every session opened in a single test."""
    engine = create_engine(
        "sqlite:///file::memory:?cache=shared&uri=true",
        future=True,
        connect_args={"uri": True},
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def session_factory(shared_engine):
    """Context-managed session factory mirroring db.session.get_session."""
    Maker = sessionmaker(shared_engine, autocommit=False, autoflush=False, expire_on_commit=False)

    @contextmanager
    def factory():
        session = Maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return factory


@pytest.fixture
def inspect_session(shared_engine):
    """Open a read-only session for test assertions, separate from cycle sessions."""
    Maker = sessionmaker(shared_engine, autocommit=False, autoflush=False, expire_on_commit=False)
    session = Maker()
    yield session
    session.close()


def _make_book_tree(tmp_path, layout: dict[str, list[str]]):
    """`layout`: relative-dir -> [filename, ...]. Creates real files for DBScanner.scan."""
    root = tmp_path / "library"
    root.mkdir()
    for rel_dir, filenames in layout.items():
        target = root if rel_dir == "" else root / rel_dir
        target.mkdir(parents=True, exist_ok=True)
        for filename in filenames:
            (target / filename).write_bytes(b"<?xml version='1.0'?><FictionBook/>")
    return root


def _ok_read(record: BookRecord) -> BookRecord:
    record.title = f"Read::{record.original_filename}"
    return record


def _ok_enrich(record: BookRecord, provider_name: str, directory_hint: Optional[dict] = None) -> BookRecord:
    record.title = f"AI::{record.original_filename}"
    record.source = "ai"
    return record


@contextmanager
def _patched_pipeline(read_side=_ok_read, enrich_side=_ok_enrich):
    """Stub read_metadata + enrich so the cycle never touches real metadata or OpenAI."""
    with patch("app.pipeline.process_file.read_metadata", side_effect=read_side), patch(
        "app.pipeline.process_file.enrich", side_effect=enrich_side
    ):
        yield


def _summary(series: str = "Series A") -> dict:
    return {
        "series_name": series,
        "universe": None,
        "genre": "scifi",
        "tags": [],
        "language": "en",
        "confidence": 0.5,
        "notes": None,
    }


def _stub_provider(summary: dict | None = None):
    """Build a MagicMock provider whose `summarize_directory` returns a known dict."""
    provider = MagicMock()
    provider.summarize_directory.return_value = summary if summary is not None else _summary()
    return provider


class TestSingleDirectoryHappyPath:
    def test_scan_job_lifecycle_pending_to_done(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2", "book2.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")

        provider = _stub_provider()
        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            result = run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.status == ScanJobStatus.done
        assert job.started_at is not None
        assert job.finished_at is not None
        assert job.files_discovered == 2
        assert job.files_processed == 2
        assert result.files_failed == 0

    def test_directory_hint_persisted_once_per_directory(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2", "book2.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        hint_data = _summary(series="Hyperion")
        provider = _stub_provider(hint_data)

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        hints = inspect_session.query(DirectoryHint).all()
        sci_fi_hints = [h for h in hints if h.directory.name == "sci-fi"]
        assert len(sci_fi_hints) == 1
        assert sci_fi_hints[0].is_current is True
        assert sci_fi_hints[0].data["series_name"] == "Hyperion"

    def test_summarize_directory_called_once_with_pending_files(
        self, tmp_path, session_factory, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2", "book2.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        # one call for "library" root (no pending files there) is skipped;
        # one call for "sci-fi" with both files.
        assert provider.summarize_directory.call_count == 1
        (call_args,) = provider.summarize_directory.call_args_list
        records = call_args.args[0]
        assert len(records) == 2
        assert {r.original_filename for r in records} == {"book1.fb2", "book2.fb2"}

    def test_files_progress_to_enriched_with_metadata_and_logs(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        files = inspect_session.query(FileRecord).all()
        assert len(files) == 1
        assert files[0].status == FileStatus.enriched


class TestHintThreadingToEnrich:
    def test_hint_passed_to_process_file_enrich(self, tmp_path, session_factory, monkeypatch):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider(_summary(series="The Expanse"))
        captured: dict = {}

        def _spy_enrich(record, provider_name, directory_hint=None):
            captured["hint"] = directory_hint
            record.source = "ai"
            return record

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), patch(
            "app.pipeline.process_file.read_metadata", side_effect=_ok_read
        ), patch("app.pipeline.process_file.enrich", side_effect=_spy_enrich):
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        assert captured["hint"] is not None
        assert captured["hint"]["series_name"] == "The Expanse"


class TestMultipleDirectories:
    def test_each_directory_gets_own_hint(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(
            tmp_path,
            {
                "sci-fi": ["a.fb2"],
                "fantasy": ["b.fb2"],
            },
        )
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        # one summarize call per directory with pending files
        assert provider.summarize_directory.call_count == 2

        hint_dirs = {
            inspect_session.get(Directory, h.directory_id).name
            for h in inspect_session.query(DirectoryHint).all()
        }
        assert hint_dirs == {"sci-fi", "fantasy"}

    def test_files_processed_count_matches_total(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(
            tmp_path,
            {
                "sci-fi": ["a.fb2", "b.fb2"],
                "fantasy": ["c.fb2"],
            },
        )
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            result = run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        assert result.files_discovered == 3
        assert result.files_processed == 3
        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.files_processed == 3


class TestFailurePaths:
    def test_one_file_failure_does_not_abort_cycle(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["ok.fb2", "broken.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        def _selective_read(record):
            if record.original_filename == "broken.fb2":
                raise RuntimeError("FB2 parse failed")
            return _ok_read(record)

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), patch(
            "app.pipeline.process_file.read_metadata", side_effect=_selective_read
        ), patch("app.pipeline.process_file.enrich", side_effect=_ok_enrich):
            result = run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        assert result.files_discovered == 2
        assert result.files_processed == 2
        assert result.files_failed == 1

        files_by_name = {
            f.filename: f for f in inspect_session.query(FileRecord).all()
        }
        assert files_by_name["ok.fb2"].status == FileStatus.enriched
        assert files_by_name["broken.fb2"].status == FileStatus.failed

        # scan job still finished cleanly
        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.status == ScanJobStatus.done

    def test_enrichment_run_recorded_per_file(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2", "b.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        runs = inspect_session.query(EnrichmentRun).all()
        assert len(runs) == 2  # one per file
        assert all(r.status == EnrichmentStatus.done for r in runs)
        assert all(r.file_count == 1 for r in runs)
        assert sum(r.success_count for r in runs) == 2


class TestEmptyTree:
    def test_empty_directory_closes_scan_job_with_zero_counts(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = tmp_path / "empty-library"
        root.mkdir()
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            result = run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        assert result.files_discovered == 0
        assert result.files_processed == 0

        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.status == ScanJobStatus.done
        provider.summarize_directory.assert_not_called()


class TestScanJobProgress:
    def test_files_discovered_set_before_processing(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2", "b.fb2", "c.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        observed_files_discovered: list[int] = []

        def _record_progress(record, provider_name, directory_hint=None):
            # capture files_discovered at the moment a file's enrich runs
            with session_factory() as s:
                job = s.query(ScanJob).first()
                observed_files_discovered.append(job.files_discovered)
            record.source = "ai"
            return record

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), patch(
            "app.pipeline.process_file.read_metadata", side_effect=_ok_read
        ), patch("app.pipeline.process_file.enrich", side_effect=_record_progress):
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        # By the time the first file is being enriched, files_discovered = 3 already
        assert observed_files_discovered == [3, 3, 3]

    def test_current_file_id_tracks_active_file(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2", "b.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        seen_current_file_ids: list[Optional[int]] = []

        def _capture_current(record, provider_name, directory_hint=None):
            with session_factory() as s:
                job = s.query(ScanJob).first()
                seen_current_file_ids.append(job.current_file_id)
            record.source = "ai"
            return record

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), patch(
            "app.pipeline.process_file.read_metadata", side_effect=_ok_read
        ), patch("app.pipeline.process_file.enrich", side_effect=_capture_current):
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        # both captured ids correspond to real FileRecord rows
        all_ids = {f.id for f in inspect_session.query(FileRecord).all()}
        assert set(seen_current_file_ids).issubset(all_ids)
        assert len(seen_current_file_ids) == 2


class TestSessionPolicy:
    def test_uses_short_sessions_not_one_long_session(
        self, tmp_path, session_factory, monkeypatch
    ):
        """Counts session opens — two files must trigger many short sessions, not one long one."""
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2", "b.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")
        provider = _stub_provider()

        open_count = 0

        @contextmanager
        def counting_factory():
            nonlocal open_count
            open_count += 1
            with session_factory() as s:
                yield s

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=counting_factory)

        # Policy: many short sessions, not one long-held. Conservative floor for 2 files.
        assert open_count >= 8


class TestEnvValidation:
    def test_missing_ai_provider_raises_before_scan_job_done(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2"]})
        monkeypatch.delenv("AI_PROVIDER", raising=False)

        with pytest.raises(RuntimeError, match="AI_PROVIDER is not set"):
            run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        # env validation runs before any scan work — the claimed job is left untouched,
        # neither failed nor advanced (it is not the cycle's job to mark its own env error).
        job = inspect_session.query(ScanJob).one()
        assert job.status == ScanJobStatus.running
        assert job.error_message is None
        assert job.finished_at is None
        assert job.files_discovered == 0


class TestScanJobFailureMarking:
    def test_cycle_exception_marks_scan_job_failed(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2"]})
        monkeypatch.setenv("AI_PROVIDER", "fake")

        provider = MagicMock()
        provider.summarize_directory.side_effect = RuntimeError("OpenAI outage")

        with patch("app.pipeline.scan_cycle.get_provider", return_value=provider), _patched_pipeline():
            with pytest.raises(RuntimeError, match="OpenAI outage"):
                run_scan_cycle(_running_job(session_factory, str(root)), str(root), session_factory=session_factory)

        job = inspect_session.query(ScanJob).first()
        assert job is not None
        assert job.status == ScanJobStatus.failed
        assert job.error_message is not None
        assert "OpenAI outage" in job.error_message
