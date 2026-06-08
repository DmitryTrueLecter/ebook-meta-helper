"""Integration: per-file analyze (enrich endpoint → watcher analyze-drain → AI enrich) on real MariaDB.

Provider is stubbed; discover is exercised end-to-end so a file reaches `read` before analyze.
"""

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
from app.models.book import BookRecord
from app.pipeline import analyze_drain
from app.pipeline.analyze_drain import drain_one_analyze
from app.pipeline.scan_cycle import run_scan_cycle
from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentRun, EnrichmentStatus, EnrichmentTrigger
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.repos import scan_job_repo


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
FB2_FIXTURE = ASSETS_DIR / "fb2" / "series.fb2"


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


@pytest.fixture
def stub_provider(monkeypatch):
    """Stub the OpenAI call: record invocations and return a deterministic AI BookRecord."""
    calls: list[BookRecord] = []

    def fake_enrich(record, provider_name, directory_hint=None):
        calls.append(record)
        ai = BookRecord(
            path=record.path,
            original_filename=record.original_filename,
            extension=record.extension,
            directories=list(record.directories),
            title="AI Suggested Title",
            authors=["AI Author"],
            language="en",
            source="ai",
            confidence=0.95,
        )
        return ai

    monkeypatch.setenv("AI_PROVIDER", "dummy")
    monkeypatch.setattr("app.pipeline.process_file.enrich", fake_enrich)
    return calls


def _client(session: Session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: session
    return TestClient(app)


def _teardown_client() -> None:
    app.dependency_overrides.pop(get_db, None)


def _discover(root: Path, factory) -> None:
    with factory() as s:
        scan_job_repo.create(s, root_path=str(root.resolve()))
        s.flush()
        job_id = scan_job_repo.claim_next_pending(s).id
    run_scan_cycle(job_id, str(root.resolve()), session_factory=factory)


def _copy(fixture: Path, target_dir: Path, name: str) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / name
    shutil.copy(fixture, dest)
    return dest


def _enrich(session: Session, file_id: int) -> dict:
    try:
        client = _client(session)
        response = client.post(f"/api/files/{file_id}/enrich")
    finally:
        _teardown_client()
    assert response.status_code == 202
    return response.json()


@pytest.fixture(autouse=True)
def _drain_uses_test_factory(monkeypatch, session_factory):
    """Point the drain's own get_session at the test engine factory."""
    monkeypatch.setattr(analyze_drain, "get_session", session_factory)


class TestAnalyzeDrainEnriches:
    def test_read_file_enrich_then_drain_lands_enriched_with_ai_snapshot(
        self, tmp_path, session, session_factory, stub_provider
    ):
        """The literal 'analysis doesn't run' regression: enrich → analyze_queued → drain → enriched."""
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")
        _discover(library, session_factory)

        record = session.execute(select(FileRecord)).scalar_one()
        assert record.status == FileStatus.read
        file_id = record.id

        body = _enrich(session, file_id)
        assert body["status"] == "analyze_queued"

        session.commit()
        assert session.get(FileRecord, file_id).status == FileStatus.analyze_queued

        result = drain_one_analyze(session_factory)
        assert result is not None
        assert result.file_id == file_id
        assert result.success is True

        session.commit()
        reloaded = session.get(FileRecord, file_id)
        assert reloaded.status == FileStatus.enriched

        # AI suggestion snapshot persisted.
        ai_snapshot = session.execute(
            select(Metadata).where(
                Metadata.file_id == file_id,
                Metadata.source == MetadataSource.ai,
                Metadata.is_current.is_(True),
            )
        ).scalar_one()
        assert ai_snapshot.title == "AI Suggested Title"

        # Exactly one OpenAI call for the one file.
        assert len(stub_provider) == 1

        # The user_file run was opened by the endpoint and closed by the drain.
        run = session.execute(select(EnrichmentRun)).scalar_one()
        assert run.trigger == EnrichmentTrigger.user_file
        assert run.status == EnrichmentStatus.done

    def test_drain_returns_none_when_queue_empty(self, session, session_factory):
        assert drain_one_analyze(session_factory) is None

    @pytest.mark.parametrize(
        "start_status",
        [
            FileStatus.enriched,
            FileStatus.accepted,
            FileStatus.rejected,
            FileStatus.failed,
        ],
    )
    def test_re_analyze_from_terminal_states(
        self, tmp_path, session, session_factory, stub_provider, start_status
    ):
        """Re-analyze from enriched/accepted/rejected/failed → analyze_queued → enriched."""
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")
        _discover(library, session_factory)

        record = session.execute(select(FileRecord)).scalar_one()
        file_id = record.id
        # Drive the file to the starting terminal/resting state.
        path = {
            FileStatus.enriched: [FileStatus.analyze_queued, FileStatus.enriching, FileStatus.enriched],
            FileStatus.accepted: [
                FileStatus.analyze_queued, FileStatus.enriching, FileStatus.enriched, FileStatus.accepted,
            ],
            FileStatus.rejected: [
                FileStatus.analyze_queued, FileStatus.enriching, FileStatus.enriched, FileStatus.rejected,
            ],
            FileStatus.failed: [FileStatus.failed],
        }[start_status]
        for status_value in path:
            record.status = status_value
        session.commit()

        _enrich(session, file_id)
        session.commit()
        assert session.get(FileRecord, file_id).status == FileStatus.analyze_queued

        result = drain_one_analyze(session_factory)
        assert result.success is True

        session.commit()
        assert session.get(FileRecord, file_id).status == FileStatus.enriched


class TestNoAutoAnalyze:
    def test_discover_never_enqueues_analyze_or_calls_provider(
        self, tmp_path, session, session_factory, stub_provider
    ):
        """Invariant: no path other than the enrich endpoint produces analyze_queued."""
        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "a.fb2")
        _copy(FB2_FIXTURE, library / "sci-fi", "b.fb2")

        _discover(library, session_factory)

        session.commit()
        statuses = [r.status for r in session.execute(select(FileRecord)).scalars()]
        assert statuses == [FileStatus.read, FileStatus.read]
        assert FileStatus.analyze_queued not in statuses

        # Provider never invoked during discover.
        assert stub_provider == []
        # No drainable work was produced by discover.
        assert drain_one_analyze(session_factory) is None


class TestNoRePickupLoop:
    def test_drain_never_reclaims_mid_pipeline_rows(self, session, session_factory):
        """No re-pickup loop: rows mid-pipeline (reading/ai_queued/enriching) are never drained."""
        directory = Directory(path="/library/sci-fi", name="sci-fi", depth=1)
        session.add(directory)
        session.flush()
        for name, status in (
            ("reading.fb2", FileStatus.reading),
            ("ai_queued.fb2", FileStatus.ai_queued),
            ("enriching.fb2", FileStatus.enriching),
        ):
            session.add(FileRecord(directory_id=directory.id, filename=name, status=status))
        session.commit()

        assert drain_one_analyze(session_factory) is None

        session.commit()
        statuses = {r.filename: r.status for r in session.execute(select(FileRecord)).scalars()}
        assert statuses == {
            "reading.fb2": FileStatus.reading,
            "ai_queued.fb2": FileStatus.ai_queued,
            "enriching.fb2": FileStatus.enriching,
        }


class TestDrainDoesNotStarveDiscover:
    def test_slow_analyze_does_not_block_discover_claim(
        self, tmp_path, session, session_factory, stub_provider
    ):
        """A pending discover job is claimed within one iteration even with analyze rows waiting."""
        from app.pipeline import watcher

        library = tmp_path / "library"
        _copy(FB2_FIXTURE, library / "sci-fi", "book.fb2")
        _discover(library, session_factory)

        # Queue the file for analyze AND enqueue a fresh discover job.
        record = session.execute(select(FileRecord)).scalar_one()
        _enrich(session, record.id)
        session.commit()

        with session_factory() as s:
            job = scan_job_repo.create(s, root_path=str(library.resolve()))
            s.flush()
            job_id = job.id

        # One iteration: discover-priority means the pending job is claimed-and-run, NOT the drain.
        # The cycle body itself is stubbed (covered by discover tests) — we assert the routing only.
        import unittest.mock as mock
        from app.pipeline.scan_cycle import CycleResult

        cycle_calls: list[int] = []

        def fake_cycle(jid, root):
            cycle_calls.append(jid)
            return CycleResult(
                scan_job_id=jid,
                files_discovered=0,
                files_read=0,
                files_failed=0,
                files_marked_missing=0,
                directories_deleted=0,
                directories_archived=0,
            )

        with mock.patch.object(watcher, "get_session", session_factory), mock.patch.object(
            watcher, "run_scan_cycle", side_effect=fake_cycle
        ), mock.patch.object(watcher, "drain_one_analyze") as drain_mock:
            watcher._run_one_iteration(str(library.resolve()))

        # The pending discover job was claimed and run this iteration; analyze was deferred.
        assert cycle_calls == [job_id]
        drain_mock.assert_not_called()

        session.commit()
        from db.models.scan_job import ScanJob, ScanJobStatus

        claimed = session.get(ScanJob, job_id)
        assert claimed.status == ScanJobStatus.running  # claimed by the iteration
        # The analyze row is still waiting — it was not starved, just deferred.
        assert session.get(FileRecord, record.id).status == FileStatus.analyze_queued
