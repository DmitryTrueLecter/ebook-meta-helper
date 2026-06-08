"""Integration: discover (FS↔DB reconcile + read metadata, NO AI) against real MariaDB + real FS."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from fastapi.testclient import TestClient

from app.api.deps import get_db
from app.api.main import app
from app.pipeline.scan_cycle import run_scan_cycle
from db.models.directory import Directory, DirectoryStatus
from db.models.enrichment_run import EnrichmentRun
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.scan_job import ScanJob, ScanJobStatus
from db.repos import scan_job_repo


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
FB2_FIXTURE = ASSETS_DIR / "fb2" / "series.fb2"
EPUB_FIXTURE = ASSETS_DIR / "epub" / "single_author.epub"


@pytest.fixture(autouse=True)
def no_ai_provider(monkeypatch):
    """Discover must never require or call OpenAI — prove the env var is irrelevant."""
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.setattr(
        "app.pipeline.process_file.enrich",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("discover called enrich()")),
    )


@pytest.fixture
def session_factory(engine: Engine):
    """Context-managed session factory mirroring db.session.get_session."""
    Maker = sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)

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


def _discover(root: Path, factory) -> "object":
    """One discover pass: enqueue + claim a job for `root`, then run the cycle."""
    with factory() as s:
        scan_job_repo.create(s, root_path=str(root.resolve()))
        s.flush()
        job_id = scan_job_repo.claim_next_pending(s).id
    return run_scan_cycle(job_id, str(root.resolve()), session_factory=factory)


def _copy(fixture: Path, target_dir: Path, name: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / name
    shutil.copy(fixture, dest)
    return dest


class TestDiscoverReadsMetadataNoAI:
    def test_new_file_ends_read_with_snapshot_zero_ai(
        self, tmp_path, session, session_factory
    ):
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")

        result = _discover(library, session_factory)

        assert result.files_discovered == 1
        assert result.files_read == 1
        assert result.files_failed == 0

        record = session.execute(select(FileRecord)).scalar_one()
        assert record.status == FileStatus.read

        snapshot = session.execute(
            select(Metadata).where(
                Metadata.file_id == record.id,
                Metadata.source == MetadataSource.file,
                Metadata.is_current.is_(True),
            )
        ).scalar_one()
        # "No metadata read" gone — a real file snapshot exists with a title.
        assert snapshot.title is not None

        # Zero AI: no AI metadata rows, no enrichment runs.
        ai_rows = session.execute(
            select(Metadata).where(Metadata.source == MetadataSource.ai)
        ).scalars().all()
        assert ai_rows == []
        assert session.execute(select(EnrichmentRun)).scalars().all() == []

        job = session.execute(select(ScanJob).where(ScanJob.id == result.scan_job_id)).scalar_one()
        assert job.status == ScanJobStatus.done

    def test_changed_file_is_re_read(self, tmp_path, session, session_factory):
        library = tmp_path / "library"
        target = _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")

        first = _discover(library, session_factory)
        assert first.files_read == 1

        record = session.execute(select(FileRecord)).scalar_one()
        first_snapshot_id = session.execute(
            select(Metadata.id).where(
                Metadata.file_id == record.id,
                Metadata.source == MetadataSource.file,
                Metadata.is_current.is_(True),
            )
        ).scalar_one()

        # Replace content with a different fixture → size/mtime change → re-read.
        shutil.copy(EPUB_FIXTURE, target)
        second = _discover(library, session_factory)
        assert second.files_read == 1

        session.commit()
        current_snapshot_id = session.execute(
            select(Metadata.id).where(
                Metadata.file_id == record.id,
                Metadata.source == MetadataSource.file,
                Metadata.is_current.is_(True),
            )
        ).scalar_one()
        assert current_snapshot_id != first_snapshot_id

    def test_content_changed_enriched_file_does_not_crash_cycle(
        self, tmp_path, session, session_factory
    ):
        """An enriched file replaced on disk is enrichment-owned: re-read must not be queued
        (would raise InvalidStatusTransition enriched->reading and crash the whole cycle)."""
        library = tmp_path / "library"
        target = _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")

        _discover(library, session_factory)
        record = session.execute(select(FileRecord)).scalar_one()
        for status_value in (
            FileStatus.analyze_queued,
            FileStatus.enriching,
            FileStatus.enriched,
        ):
            record.status = status_value
        session.commit()
        record_id = record.id

        # Replace content → size/mtime change. Discover must survive and leave the
        # enrichment-owned status untouched (not re-queued through the read pipeline).
        shutil.copy(EPUB_FIXTURE, target)
        result = _discover(library, session_factory)
        assert result.files_discovered == 0
        assert result.files_read == 0
        assert result.files_failed == 0

        session.commit()
        reloaded = session.execute(select(FileRecord)).scalar_one()
        assert reloaded.id == record_id
        assert reloaded.status == FileStatus.enriched
        # Size still refreshed in the DB even though no re-read happened.
        assert reloaded.size == target.stat().st_size


class TestStrandedPendingRecovery:
    def test_stranded_pending_unchanged_file_is_read(
        self, tmp_path, session, session_factory
    ):
        """A `pending` row whose on-disk bytes never changed (crashed earlier cycle)
        must be read on the next discover, not left stuck in `pending` forever."""
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")

        # First discover reads it; force it back to `pending` to simulate a row
        # stranded by an earlier crashed cycle (read never completed).
        _discover(library, session_factory)
        record = session.execute(select(FileRecord)).scalar_one()
        record.status = FileStatus.pending
        session.commit()
        record_id = record.id

        # Same bytes on disk — content snapshot is unchanged.
        result = _discover(library, session_factory)
        assert result.files_discovered == 1
        assert result.files_read == 1
        assert result.files_failed == 0

        session.commit()
        reloaded = session.execute(select(FileRecord)).scalar_one()
        assert reloaded.id == record_id
        assert reloaded.status == FileStatus.read

    def test_already_read_unchanged_file_is_not_re_read(
        self, tmp_path, session, session_factory
    ):
        """An already-`read` file with unchanged bytes is not re-queued — no needless re-work."""
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")

        first = _discover(library, session_factory)
        assert first.files_read == 1

        # Re-discover with no on-disk change.
        second = _discover(library, session_factory)
        assert second.files_discovered == 0
        assert second.files_read == 0
        assert second.files_failed == 0

        session.commit()
        assert session.execute(select(FileRecord)).scalar_one().status == FileStatus.read


class TestFileReconcile:
    def test_gone_read_file_marked_missing_history_preserved(
        self, tmp_path, session, session_factory
    ):
        library = tmp_path / "library"
        keep = _copy(FB2_FIXTURE, library / "sci-fi", "keep.fb2")
        gone = _copy(FB2_FIXTURE, library / "sci-fi", "gone.fb2")

        _discover(library, session_factory)
        gone_record = session.execute(
            select(FileRecord).where(FileRecord.filename == "gone.fb2")
        ).scalar_one()
        gone_id = gone_record.id

        gone.unlink()
        result = _discover(library, session_factory)
        assert result.files_marked_missing == 1

        session.commit()
        by_name = {
            r.filename: r for r in session.execute(select(FileRecord)).scalars()
        }
        assert by_name["gone.fb2"].status == FileStatus.missing
        assert by_name["keep.fb2"].status == FileStatus.read
        # Row + its snapshot history survive.
        assert by_name["gone.fb2"].id == gone_id
        assert session.execute(
            select(Metadata).where(Metadata.file_id == gone_id)
        ).scalars().all() != []

    def test_accepted_file_absent_not_marked_missing(
        self, tmp_path, session, session_factory
    ):
        """An accepted file legitimately moved to BOOKS_READY_DIR — must NOT be marked missing."""
        library = tmp_path / "library"
        moved = _copy(FB2_FIXTURE, library / "sci-fi", "accepted.fb2")

        _discover(library, session_factory)
        record = session.execute(select(FileRecord)).scalar_one()
        # Drive it to accepted through the lifecycle.
        for status_value in (
            FileStatus.analyze_queued,
            FileStatus.enriching,
            FileStatus.enriched,
            FileStatus.accepted,
        ):
            record.status = status_value
        session.commit()

        moved.unlink()  # accepted file removed from source
        result = _discover(library, session_factory)
        assert result.files_marked_missing == 0

        session.commit()
        reloaded = session.execute(select(FileRecord)).scalar_one()
        assert reloaded.status == FileStatus.accepted

    def test_reappearance_returns_to_read(self, tmp_path, session, session_factory):
        library = tmp_path / "library"
        target = _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")

        _discover(library, session_factory)
        target.unlink()
        _discover(library, session_factory)
        session.commit()
        assert session.execute(select(FileRecord)).scalar_one().status == FileStatus.missing

        shutil.copy(FB2_FIXTURE, target)
        _discover(library, session_factory)
        session.commit()
        assert session.execute(select(FileRecord)).scalar_one().status == FileStatus.read

    def test_subtree_scoping_no_sibling_prefix_cross_match(
        self, tmp_path, session, session_factory
    ):
        """Discovering /books/sci must not touch files under the sibling /books/science."""
        books = tmp_path / "books"
        _copy(FB2_FIXTURE, books / "sci", "a.fb2")
        science_file = _copy(FB2_FIXTURE, books / "science", "b.fb2")

        # Discover the whole tree first so both files land `read`.
        _discover(books, session_factory)

        # Now discover ONLY the /books/sci subtree. The sibling /books/science file
        # is absent from this scan's present-set but lies outside the scoped subtree —
        # it must NOT be marked missing.
        result = _discover(books / "sci", session_factory)
        assert result.files_marked_missing == 0

        session.commit()
        science_record = session.execute(
            select(FileRecord).where(FileRecord.filename == "b.fb2")
        ).scalar_one()
        assert science_record.status == FileStatus.read
        assert science_file.exists()


class TestDirectoryReconcile:
    def _client(self, session):
        app.dependency_overrides[get_db] = lambda: session
        return TestClient(app)

    def _teardown_client(self):
        app.dependency_overrides.pop(get_db, None)

    def test_history_free_gone_directory_hard_deleted(
        self, tmp_path, session, session_factory
    ):
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "keep", "a.fb2")
        gone_dir = library / "gone"
        _copy(FB2_FIXTURE, gone_dir, "b.fb2")

        _discover(library, session_factory)
        gone_paths_before = session.execute(
            select(Directory.path).where(Directory.path == str(gone_dir.resolve()))
        ).scalars().all()
        assert gone_paths_before  # it was registered

        shutil.rmtree(gone_dir)
        result = _discover(library, session_factory)
        assert result.directories_deleted >= 1

        session.commit()
        # Hard-deleted: absent from the DB entirely.
        assert session.execute(
            select(Directory).where(Directory.path == str(gone_dir.resolve()))
        ).scalars().all() == []

        # Absent from GET /api/directories.
        try:
            client = self._client(session)
            body = client.get("/api/directories").json()
        finally:
            self._teardown_client()
        all_paths = _collect_paths(body)
        assert str(gone_dir.resolve()) not in all_paths

    def test_accepted_owning_gone_directory_archived(
        self, tmp_path, session, session_factory
    ):
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "keep", "a.fb2")
        gone_dir = library / "archived"
        _copy(FB2_FIXTURE, gone_dir, "b.fb2")

        _discover(library, session_factory)
        # Make the file in gone_dir history-bearing (accepted).
        record = session.execute(
            select(FileRecord).join(Directory).where(Directory.path == str(gone_dir.resolve()))
        ).scalar_one()
        for status_value in (
            FileStatus.analyze_queued,
            FileStatus.enriching,
            FileStatus.enriched,
            FileStatus.accepted,
        ):
            record.status = status_value
        session.commit()

        shutil.rmtree(gone_dir)
        result = _discover(library, session_factory)
        assert result.directories_archived >= 1
        assert result.directories_deleted == 0

        session.commit()
        archived = session.execute(
            select(Directory).where(Directory.path == str(gone_dir.resolve()))
        ).scalar_one()
        assert archived.status == DirectoryStatus.missing
        # History survives.
        assert session.execute(
            select(FileRecord).where(FileRecord.id == record.id)
        ).scalar_one().status == FileStatus.accepted

        # Hidden by default, visible with include_missing.
        try:
            client = self._client(session)
            default_paths = _collect_paths(client.get("/api/directories").json())
            with_missing_paths = _collect_paths(
                client.get("/api/directories?include_missing=true").json()
            )
        finally:
            self._teardown_client()
        assert str(gone_dir.resolve()) not in default_paths
        assert str(gone_dir.resolve()) in with_missing_paths

    def test_nested_gone_directory_bottom_up_hard_deleted(
        self, tmp_path, session, session_factory
    ):
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "keep", "a.fb2")
        nested = library / "gone" / "deeper"
        _copy(FB2_FIXTURE, nested, "b.fb2")

        _discover(library, session_factory)
        shutil.rmtree(library / "gone")
        result = _discover(library, session_factory)
        # Both the parent `gone` and child `deeper` are history-free → hard-deleted.
        assert result.directories_deleted >= 2

        session.commit()
        remaining = session.execute(select(Directory.path)).scalars().all()
        assert str((library / "gone").resolve()) not in remaining
        assert str(nested.resolve()) not in remaining
        assert str((library / "keep").resolve()) in remaining


def _collect_paths(nodes: list) -> set[str]:
    paths: set[str] = set()
    for node in nodes:
        paths.add(node["path"])
        paths |= _collect_paths(node.get("children", []))
    return paths
