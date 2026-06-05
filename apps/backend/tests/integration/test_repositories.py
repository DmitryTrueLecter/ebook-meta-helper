"""Repository invariants verified against real MariaDB (unit suite uses SQLite which cannot enforce CASCADE/JSON)."""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from db.models.directory import Directory
from db.models.directory_hint import DirectoryHint
from db.models.enrichment_run import (
    EnrichmentRun,
    EnrichmentStatus,
    EnrichmentTrigger,
)
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import (
    ProcessingLog,
    ProcessingLogLevel,
    ProcessingStep,
)
from db.models.scan_job import ScanJob, ScanJobStatus
from db.repos import (
    directory_hint_repo,
    directory_repo,
    enrichment_run_repo,
    file_repo,
    log_repo,
    metadata_repo,
    scan_job_repo,
)
from db.repos.directory_hint_repo import DirectoryHintInput
from db.repos.directory_repo import DirectoryInput
from db.repos.enrichment_run_repo import EnrichmentRunInput, EnrichmentRunResult
from db.repos.file_repo import FileAttrs, InvalidStatusTransition
from db.repos.log_repo import LogEntry
from db.repos.metadata_repo import MetadataInput, MetadataScalars
from db.repos.scan_job_repo import ScanProgress


def _make_directory(session: Session, path: str = "/library/books") -> Directory:
    spec = DirectoryInput(
        path=path, name=path.rsplit("/", 1)[-1] or "root", parent_id=None, depth=0
    )
    return directory_repo.get_or_create(session, spec)


def _make_file(
    session: Session, directory: Directory, filename: str = "book.epub"
) -> FileRecord:
    return file_repo.get_or_create(
        session,
        directory.id,
        filename,
        FileAttrs(extension="epub", format="EPUB 3.0", size=1024, hash="a" * 64),
    )


class TestMetadataIsCurrentUniqueness:
    """A second metadata row for the same (file_id, source) flips the prior current row off."""

    def test_second_ai_insert_flips_first(self, session):
        directory = _make_directory(session)
        file_record = _make_file(session, directory)

        first = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.ai,
                data={"authors": ["A"]},
                scalars=MetadataScalars(title="V1", confidence=None),
            ),
        )
        second = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.ai,
                data={"authors": ["A2"]},
                scalars=MetadataScalars(title="V2", confidence=None),
            ),
        )
        session.commit()

        session.refresh(first)
        session.refresh(second)
        assert first.is_current is False
        assert second.is_current is True

        current_rows = session.execute(
            select(Metadata).where(
                Metadata.file_id == file_record.id,
                Metadata.source == MetadataSource.ai,
                Metadata.is_current.is_(True),
            )
        ).scalars().all()
        assert len(current_rows) == 1
        assert current_rows[0].id == second.id

    def test_different_sources_kept_independent(self, session):
        """`file` source remains current when a new `ai` row is inserted."""
        directory = _make_directory(session)
        file_record = _make_file(session, directory)

        file_meta = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.file,
                data={"raw": True},
            ),
        )
        ai_meta = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.ai,
                data={"enriched": True},
            ),
        )
        session.commit()
        session.refresh(file_meta)
        session.refresh(ai_meta)

        assert file_meta.is_current is True
        assert ai_meta.is_current is True

    def test_third_insert_only_flips_prior_current(self, session):
        """Earlier non-current rows stay non-current; only the most recent prior current flips."""
        directory = _make_directory(session)
        file_record = _make_file(session, directory)

        v1 = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id, source=MetadataSource.ai, data={"v": 1}
            ),
        )
        v2 = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id, source=MetadataSource.ai, data={"v": 2}
            ),
        )
        v3 = metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id, source=MetadataSource.ai, data={"v": 3}
            ),
        )
        session.commit()
        session.refresh(v1)
        session.refresh(v2)
        session.refresh(v3)

        assert (v1.is_current, v2.is_current, v3.is_current) == (False, False, True)


class TestDirectoryHintIsCurrentUniqueness:
    def test_second_hint_flips_first(self, session):
        directory = _make_directory(session)

        first = directory_hint_repo.create(
            session,
            DirectoryHintInput(directory_id=directory.id, data={"summary": "v1"}),
        )
        second = directory_hint_repo.create(
            session,
            DirectoryHintInput(directory_id=directory.id, data={"summary": "v2"}),
        )
        session.commit()
        session.refresh(first)
        session.refresh(second)

        assert first.is_current is False
        assert second.is_current is True

        current = directory_hint_repo.get_current(session, directory.id)
        assert current is not None and current.id == second.id

    def test_hints_scoped_by_directory(self, session):
        d1 = _make_directory(session, "/lib/a")
        d2 = _make_directory(session, "/lib/b")

        h1 = directory_hint_repo.create(
            session, DirectoryHintInput(directory_id=d1.id, data={"x": 1})
        )
        h2 = directory_hint_repo.create(
            session, DirectoryHintInput(directory_id=d2.id, data={"x": 2})
        )
        session.commit()

        session.refresh(h1)
        session.refresh(h2)
        # New hint on d2 must not flip d1's hint.
        assert h1.is_current is True
        assert h2.is_current is True


class TestFileStatusStateMachine:
    def test_invalid_transition_predicate_returns_false(self):
        assert file_repo.transition(FileStatus.pending, FileStatus.accepted) is False
        assert file_repo.transition(FileStatus.accepted, FileStatus.rejected) is False

    def test_valid_transition_predicate_returns_true(self):
        assert file_repo.transition(FileStatus.pending, FileStatus.reading) is True
        assert file_repo.transition(FileStatus.enriched, FileStatus.accepted) is True

    def test_update_status_rejects_invalid_move(self, session):
        directory = _make_directory(session)
        file_record = _make_file(session, directory)
        session.commit()
        file_id = file_record.id

        # pending -> accepted is not in the allowed-edge list
        with pytest.raises(InvalidStatusTransition) as exc:
            file_repo.update_status(session, file_id, FileStatus.accepted)
        assert exc.value.from_status == FileStatus.pending
        assert exc.value.to_status == FileStatus.accepted

        session.rollback()
        reloaded = session.get(FileRecord, file_id)
        assert reloaded is not None
        assert reloaded.status == FileStatus.pending

    def test_update_status_persists_valid_move(self, session):
        directory = _make_directory(session)
        file_record = _make_file(session, directory)
        file_repo.update_status(session, file_record.id, FileStatus.reading)
        session.commit()
        session.refresh(file_record)
        assert file_record.status == FileStatus.reading


class TestCascadeDeletes:
    """Deleting a Directory removes every descendant row through the FK chain."""

    def test_directory_delete_removes_all_descendants(self, session):
        directory = _make_directory(session)
        file_record = _make_file(session, directory)
        directory_hint_repo.create(
            session,
            DirectoryHintInput(directory_id=directory.id, data={"summary": "x"}),
        )
        metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id, source=MetadataSource.file, data={"raw": True}
            ),
        )
        log_repo.write(
            session,
            LogEntry(
                file_id=file_record.id,
                step=ProcessingStep.read_metadata,
                level=ProcessingLogLevel.info,
                message="ok",
            ),
        )
        session.commit()

        # Snapshot ids before DELETE — accessing ORM attributes after the row is gone triggers an expired-attribute reload that fails.
        directory_id = directory.id
        file_id = file_record.id

        # Raw DELETE proves FK CASCADE — ORM-level cascade would delete children in Python first.
        session.execute(
            text("DELETE FROM directories WHERE id = :id"), {"id": directory_id}
        )
        session.commit()

        assert session.execute(
            text("SELECT COUNT(*) FROM directories WHERE id = :id"),
            {"id": directory_id},
        ).scalar() == 0
        assert session.execute(
            text("SELECT COUNT(*) FROM directory_hints WHERE directory_id = :id"),
            {"id": directory_id},
        ).scalar() == 0
        assert session.execute(
            text("SELECT COUNT(*) FROM file_records WHERE directory_id = :id"),
            {"id": directory_id},
        ).scalar() == 0
        assert session.execute(
            text("SELECT COUNT(*) FROM metadata WHERE file_id = :id"),
            {"id": file_id},
        ).scalar() == 0
        assert session.execute(
            text("SELECT COUNT(*) FROM processing_logs WHERE file_id = :id"),
            {"id": file_id},
        ).scalar() == 0

    def test_file_delete_removes_metadata_and_logs(self, session):
        directory = _make_directory(session)
        file_record = _make_file(session, directory)
        metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id, source=MetadataSource.file, data={"x": 1}
            ),
        )
        log_repo.write(
            session,
            LogEntry(
                file_id=file_record.id,
                step=ProcessingStep.read_metadata,
                message="ok",
            ),
        )
        session.commit()

        file_id = file_record.id
        session.execute(
            text("DELETE FROM file_records WHERE id = :id"), {"id": file_id}
        )
        session.commit()

        assert session.execute(
            text("SELECT COUNT(*) FROM metadata WHERE file_id = :id"),
            {"id": file_id},
        ).scalar() == 0
        assert session.execute(
            text("SELECT COUNT(*) FROM processing_logs WHERE file_id = :id"),
            {"id": file_id},
        ).scalar() == 0


class TestFullPipelineSimulation:
    """Walk a file through every status; verify history accumulation."""

    def test_pipeline_walk_creates_metadata_history(self, session):
        directory = _make_directory(session, "/lib/walk")
        directory_hint_repo.create(
            session,
            DirectoryHintInput(
                directory_id=directory.id,
                data={"summary": "tech books"},
                ai_model="gpt-4",
            ),
        )
        file_record = _make_file(session, directory, "walk.epub")

        for next_status in (
            FileStatus.reading,
            FileStatus.ai_queued,
            FileStatus.enriching,
            FileStatus.enriched,
            FileStatus.accepted,
        ):
            file_repo.update_status(session, file_record.id, next_status)
        session.commit()
        session.refresh(file_record)
        assert file_record.status == FileStatus.accepted

        run = enrichment_run_repo.create(
            session,
            EnrichmentRunInput(
                directory_id=directory.id, trigger=EnrichmentTrigger.scan
            ),
        )
        metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id, source=MetadataSource.file, data={"raw": True}
            ),
        )
        metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.ai,
                data={"enriched": True},
                enrichment_run_id=run.id,
            ),
        )
        metadata_repo.create(
            session,
            MetadataInput(
                file_id=file_record.id,
                source=MetadataSource.accepted,
                data={"final": True},
            ),
        )
        session.commit()

        history = metadata_repo.get_history(session, file_record.id)
        sources = {m.source for m in history}
        assert sources == {
            MetadataSource.file,
            MetadataSource.ai,
            MetadataSource.accepted,
        }
        # All three remain `is_current=True` because they belong to different sources.
        assert all(m.is_current for m in history)


class TestGetCurrentReturnsLatest:
    def test_returns_latest_after_repeated_updates(self, session):
        directory = _make_directory(session)
        file_record = _make_file(session, directory)

        latest_data = None
        for i in range(4):
            payload = {"v": i}
            metadata_repo.create(
                session,
                MetadataInput(
                    file_id=file_record.id,
                    source=MetadataSource.ai,
                    data=payload,
                ),
            )
            latest_data = payload
        session.commit()

        current = metadata_repo.get_current(
            session, file_record.id, MetadataSource.ai
        )
        assert current is not None
        assert current.data == latest_data
        assert current.is_current is True


class TestGetTreeHierarchy:
    def test_returns_directories_ordered_by_depth(self, session):
        root = directory_repo.get_or_create(
            session,
            DirectoryInput(path="/lib", name="lib", parent_id=None, depth=0),
        )
        child_a = directory_repo.get_or_create(
            session,
            DirectoryInput(
                path="/lib/a", name="a", parent_id=root.id, depth=1
            ),
        )
        child_b = directory_repo.get_or_create(
            session,
            DirectoryInput(
                path="/lib/b", name="b", parent_id=root.id, depth=1
            ),
        )
        grand = directory_repo.get_or_create(
            session,
            DirectoryInput(
                path="/lib/a/x", name="x", parent_id=child_a.id, depth=2
            ),
        )
        session.commit()

        tree = directory_repo.get_tree(session)
        depths = [d.depth for d in tree]
        # Depth-ascending order is the contract.
        assert depths == sorted(depths)

        by_path = {d.path: d for d in tree}
        assert by_path["/lib"].children
        root_children_ids = {c.id for c in by_path["/lib"].children}
        assert root_children_ids == {child_a.id, child_b.id}
        assert {c.id for c in by_path["/lib/a"].children} == {grand.id}
        assert by_path["/lib/b"].children == []


class TestScanJobLifecycle:
    def test_create_start_progress_finish(self, session):
        root = _make_directory(session, "/lib/scan")

        job = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        session.commit()
        assert job.status == ScanJobStatus.pending
        assert job.started_at is None

        scan_job_repo.start(session, job.id)
        session.commit()
        session.refresh(job)
        assert job.status == ScanJobStatus.running
        assert job.started_at is not None
        assert scan_job_repo.get_active(session) is not None
        assert scan_job_repo.get_active(session).id == job.id

        scan_job_repo.update_progress(
            session,
            job.id,
            ScanProgress(files_discovered=10, files_processed=3),
        )
        session.commit()
        session.refresh(job)
        assert job.files_discovered == 10
        assert job.files_processed == 3

        scan_job_repo.finish(session, job.id)
        session.commit()
        session.refresh(job)
        assert job.status == ScanJobStatus.done
        assert job.finished_at is not None
        # finished jobs are no longer "active"
        assert scan_job_repo.get_active(session) is None

    def test_start_rejects_non_pending(self, session):
        root = _make_directory(session, "/lib/scan2")
        job = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        scan_job_repo.start(session, job.id)
        session.commit()

        with pytest.raises(ValueError):
            scan_job_repo.start(session, job.id)

    def test_find_active_or_pending_prefers_running_then_pending(self, session):
        root = _make_directory(session, "/lib/scan3")
        pending = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        running = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        scan_job_repo.start(session, running.id)
        session.commit()

        found = scan_job_repo.find_active_or_pending(session)
        assert found is not None
        assert found.id == running.id

        scan_job_repo.finish(session, running.id)
        session.commit()
        found = scan_job_repo.find_active_or_pending(session)
        assert found is not None
        assert found.id == pending.id

    def test_find_active_or_pending_none_when_only_completed(self, session):
        root = _make_directory(session, "/lib/scan4")
        job = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        scan_job_repo.start(session, job.id)
        scan_job_repo.finish(session, job.id)
        session.commit()

        assert scan_job_repo.find_active_or_pending(session) is None

    def test_find_latest_completed_returns_most_recent_terminal(self, session):
        root = _make_directory(session, "/lib/scan5")
        first = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        scan_job_repo.start(session, first.id)
        scan_job_repo.finish(session, first.id)
        session.commit()

        second = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        scan_job_repo.start(session, second.id)
        scan_job_repo.fail(session, second.id, "boom")
        session.commit()

        found = scan_job_repo.find_latest_completed(session)
        assert found is not None
        assert found.id == second.id

    def test_find_latest_completed_ignores_running_and_pending(self, session):
        root = _make_directory(session, "/lib/scan6")
        scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        running = scan_job_repo.create(session, root_path=root.path, root_directory_id=root.id)
        scan_job_repo.start(session, running.id)
        session.commit()

        assert scan_job_repo.find_latest_completed(session) is None


class TestEnrichmentRunLifecycle:
    """Covered as part of pipeline orchestration — open via create, close via finish/fail."""

    def test_finish_sets_counters_and_status(self, session):
        directory = _make_directory(session)
        run = enrichment_run_repo.create(
            session,
            EnrichmentRunInput(
                directory_id=directory.id, trigger=EnrichmentTrigger.scan
            ),
        )
        session.commit()
        assert run.status == EnrichmentStatus.running

        enrichment_run_repo.finish(
            session,
            run.id,
            EnrichmentRunResult(success_count=5, failure_count=1),
        )
        session.commit()
        session.refresh(run)
        assert run.status == EnrichmentStatus.done
        assert run.success_count == 5
        assert run.failure_count == 1
        assert run.finished_at is not None

    def test_finish_rejects_already_closed(self, session):
        directory = _make_directory(session)
        run = enrichment_run_repo.create(
            session,
            EnrichmentRunInput(
                directory_id=directory.id, trigger=EnrichmentTrigger.scan
            ),
        )
        enrichment_run_repo.fail(session, run.id, "boom")
        session.commit()

        with pytest.raises(ValueError):
            enrichment_run_repo.finish(
                session,
                run.id,
                EnrichmentRunResult(success_count=0, failure_count=0),
            )
