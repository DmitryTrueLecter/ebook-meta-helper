"""End-to-end pipeline integration: real MariaDB + DummyProvider, no OpenAI."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.pipeline import scan_cycle, watcher
from app.pipeline.scan_cycle import run_scan_cycle
from db.repos import scan_job_repo
from db.models.directory import Directory
from db.models.directory_hint import DirectoryHint
from db.models.enrichment_run import EnrichmentRun
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import ProcessingLog, ProcessingStep
from db.models.scan_job import ScanJob, ScanJobStatus


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
FIXTURE_FILES = (
    ASSETS_DIR / "epub" / "single_author.epub",
    ASSETS_DIR / "fb2" / "no_namespace.fb2",
    ASSETS_DIR / "fb2" / "series.fb2",
)


@pytest.fixture
def book_library(tmp_path: Path) -> Path:
    """Copy three real ebook assets into a fresh `library/` directory."""
    library = tmp_path / "library"
    library.mkdir()
    for source in FIXTURE_FILES:
        shutil.copy(source, library / source.name)
    return library


@pytest.fixture
def test_session_factory(engine: Engine):
    """Context-managed session factory mirroring `db.session.get_session`."""
    Maker = sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)

    @contextmanager
    def factory() -> Generator[Session, None, None]:
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
def patched_watcher_session(engine: Engine, monkeypatch):
    """Point `watcher.get_session` at the test engine so init helpers hit MariaDB."""
    Maker = sessionmaker(engine, autocommit=False, autoflush=False, expire_on_commit=False)

    @contextmanager
    def factory() -> Generator[Session, None, None]:
        session = Maker()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(watcher, "get_session", factory)


def _run_one_watch_iteration(library: Path, factory) -> scan_cycle.CycleResult:
    """One pass equivalent to a single `run_watcher` tick — enqueue, claim, run; no sleep loop."""
    with factory() as session:
        scan_job_repo.create(session, root_path=str(library))
        session.flush()
        job_id = scan_job_repo.claim_next_pending(session).id
    return run_scan_cycle(job_id, str(library), session_factory=factory)


class TestDiscoverEndToEnd:
    """Three real ebooks land in DB as `read` with file-metadata snapshots — NO AI."""

    def test_discover_reads_file_metadata_no_ai(
        self,
        book_library: Path,
        session: Session,
        test_session_factory,
        monkeypatch,
    ):
        # AI_PROVIDER absent must not matter — discover never calls OpenAI.
        monkeypatch.delenv("AI_PROVIDER", raising=False)

        result = _run_one_watch_iteration(book_library, test_session_factory)

        assert result.files_discovered == 3
        assert result.files_read == 3
        assert result.files_failed == 0

        directory = session.execute(
            select(Directory).where(Directory.path == str(book_library.resolve()))
        ).scalar_one()
        assert directory.name == "library"
        assert directory.depth is not None

        # Discover writes NO directory hints (those were the dropped per-directory AI call).
        hints = session.execute(
            select(DirectoryHint).where(DirectoryHint.directory_id == directory.id)
        ).scalars().all()
        assert hints == []

        files = session.execute(
            select(FileRecord).where(FileRecord.directory_id == directory.id)
        ).scalars().all()
        assert len(files) == 3
        assert all(f.status == FileStatus.read for f in files)
        assert {f.filename for f in files} == {
            "single_author.epub",
            "no_namespace.fb2",
            "series.fb2",
        }

        for file_record in files:
            metadata_rows = session.execute(
                select(Metadata).where(Metadata.file_id == file_record.id)
            ).scalars().all()
            sources = {m.source for m in metadata_rows if m.is_current}
            # Only the `file` snapshot exists — no `ai` row during discover.
            assert sources == {MetadataSource.file}, (
                f"file {file_record.filename}: expected only a current `file` row, got {sources}"
            )

            log_steps = {
                log.step
                for log in session.execute(
                    select(ProcessingLog).where(ProcessingLog.file_id == file_record.id)
                ).scalars()
            }
            assert ProcessingStep.read_metadata in log_steps
            assert ProcessingStep.ai_enrich not in log_steps

        scan_job = session.execute(
            select(ScanJob).where(ScanJob.id == result.scan_job_id)
        ).scalar_one()
        assert scan_job.status == ScanJobStatus.done

        # No enrichment runs created by discover.
        assert session.execute(select(EnrichmentRun)).scalars().all() == []


class TestCrashRecovery:
    """An `enriching` row left over from a prior crash must be reset before processing."""

    def test_watcher_init_resets_stalled_enriching_to_analyze_queued(
        self,
        book_library: Path,
        session: Session,
        test_session_factory,
        patched_watcher_session,
        monkeypatch,
    ):
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        _run_one_watch_iteration(book_library, test_session_factory)
        session.expire_all()

        target = session.execute(
            select(FileRecord).where(FileRecord.filename == "single_author.epub")
        ).scalar_one()
        target.status = FileStatus.enriching
        session.commit()

        reset_count = watcher._reset_stalled_on_startup()
        assert reset_count == 1

        # Drop REPEATABLE READ snapshot so the watcher's commit is visible below.
        session.commit()
        session.expire_all()
        recovered = session.execute(
            select(FileRecord).where(FileRecord.id == target.id)
        ).scalar_one()
        assert recovered.status == FileStatus.analyze_queued
        assert recovered.error_message is None
