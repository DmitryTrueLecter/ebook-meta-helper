"""Unit tests for app.pipeline.scan_cycle — discover-only cycle (walk + read metadata, NO AI)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.book import BookRecord
from app.pipeline.scan_cycle import run_scan_cycle
from db.base import Base
import db.models  # noqa: F401 — register all models with Base.metadata
from db.models.directory import Directory, DirectoryStatus
from db.models.metadata import Metadata, MetadataSource
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


@contextmanager
def _patched_read(read_side=_ok_read):
    """Stub read_metadata so the cycle never touches real metadata parsing."""
    with patch("app.pipeline.process_file.read_metadata", side_effect=read_side):
        yield


@contextmanager
def _no_enrich_guard():
    """Fail the test if enrich is ever called — discover must never invoke AI."""

    def _boom(*_args, **_kwargs):
        raise AssertionError("enrich() must not be called during discover")

    with patch("app.pipeline.process_file.enrich", side_effect=_boom):
        yield


class TestDiscoverReadsMetadataNoAI:
    def test_new_files_land_read_with_file_snapshot(
        self, tmp_path, session_factory, inspect_session
    ):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2", "book2.fb2"]})

        with _patched_read(), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        assert result.files_discovered == 2
        assert result.files_read == 2
        assert result.files_failed == 0

        files = inspect_session.query(FileRecord).all()
        assert {f.status for f in files} == {FileStatus.read}
        for record in files:
            snapshot = inspect_session.query(Metadata).filter(
                Metadata.file_id == record.id,
                Metadata.source == MetadataSource.file,
                Metadata.is_current.is_(True),
            ).one()
            assert snapshot.title == f"Read::{record.filename}"

    def test_scan_job_finishes_done(self, tmp_path, session_factory, inspect_session):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book1.fb2"]})

        with _patched_read(), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.status == ScanJobStatus.done
        assert job.started_at is not None
        assert job.finished_at is not None

    def test_discover_requires_no_ai_provider_env(
        self, tmp_path, session_factory, inspect_session, monkeypatch
    ):
        """AI_PROVIDER absent must not break discover — it never touches OpenAI."""
        monkeypatch.delenv("AI_PROVIDER", raising=False)
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2"]})

        with _patched_read(), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        assert result.files_read == 1
        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.status == ScanJobStatus.done


class TestChangedFileReRead:
    def test_changed_file_is_re_read(self, tmp_path, session_factory, inspect_session):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book.fb2"]})

        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        # Mutate the file so its size/mtime differ — discover must re-read it.
        (root / "sci-fi" / "book.fb2").write_bytes(
            b"<?xml version='1.0'?><FictionBook>changed</FictionBook>"
        )

        reads: list[str] = []

        def _track_read(record: BookRecord) -> BookRecord:
            reads.append(record.original_filename)
            record.title = "re-read"
            return record

        with _patched_read(_track_read), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        assert reads == ["book.fb2"]
        assert result.files_read == 1

    def test_unchanged_file_not_re_read(self, tmp_path, session_factory):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book.fb2"]})

        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        reads: list[str] = []

        def _track_read(record: BookRecord) -> BookRecord:
            reads.append(record.original_filename)
            return record

        with _patched_read(_track_read), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        assert reads == []
        assert result.files_discovered == 0


class TestFileReconcile:
    def test_gone_read_file_marked_missing(self, tmp_path, session_factory, inspect_session):
        root = _make_book_tree(tmp_path, {"sci-fi": ["keep.fb2", "gone.fb2"]})

        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        (root / "sci-fi" / "gone.fb2").unlink()

        with _patched_read(), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        assert result.files_marked_missing == 1
        by_name = {f.filename: f for f in inspect_session.query(FileRecord).all()}
        assert by_name["gone.fb2"].status == FileStatus.missing
        assert by_name["keep.fb2"].status == FileStatus.read

    def test_reappeared_file_back_to_read(self, tmp_path, session_factory, inspect_session):
        root = _make_book_tree(tmp_path, {"sci-fi": ["book.fb2"]})
        target = root / "sci-fi" / "book.fb2"

        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )
        target.unlink()
        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )
        inspect_session.expire_all()
        gone = inspect_session.query(FileRecord).filter_by(filename="book.fb2").one()
        assert gone.status == FileStatus.missing

        target.write_bytes(b"<?xml version='1.0'?><FictionBook/>")
        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        inspect_session.expire_all()
        recovered = inspect_session.query(FileRecord).filter_by(filename="book.fb2").one()
        assert recovered.status == FileStatus.read


class TestEmptyTree:
    def test_empty_directory_closes_scan_job_with_zero_counts(
        self, tmp_path, session_factory, inspect_session
    ):
        root = tmp_path / "empty-library"
        root.mkdir()

        with _patched_read(), _no_enrich_guard():
            result = run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=session_factory
            )

        assert result.files_discovered == 0
        assert result.files_read == 0
        job = inspect_session.get(ScanJob, result.scan_job_id)
        assert job.status == ScanJobStatus.done


class TestScanJobFailureMarking:
    def test_cycle_exception_marks_scan_job_failed(self, tmp_path, session_factory, inspect_session):
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2"]})

        with patch(
            "app.pipeline.scan_cycle.DBScanner", side_effect=RuntimeError("disk exploded")
        ):
            with pytest.raises(RuntimeError, match="disk exploded"):
                run_scan_cycle(
                    _running_job(session_factory, str(root)), str(root), session_factory=session_factory
                )

        job = inspect_session.query(ScanJob).first()
        assert job is not None
        assert job.status == ScanJobStatus.failed
        assert "disk exploded" in job.error_message


class TestSessionPolicy:
    def test_uses_short_sessions_not_one_long_session(self, tmp_path, session_factory):
        """Counts session opens — discovering two files must use many short sessions."""
        root = _make_book_tree(tmp_path, {"sci-fi": ["a.fb2", "b.fb2"]})

        open_count = 0

        @contextmanager
        def counting_factory():
            nonlocal open_count
            open_count += 1
            with session_factory() as s:
                yield s

        with _patched_read(), _no_enrich_guard():
            run_scan_cycle(
                _running_job(session_factory, str(root)), str(root), session_factory=counting_factory
            )

        # Policy: many short sessions, not one long-held. Walk + per-file reads + reconcile.
        assert open_count >= 8
