"""Schema-level tests: model definitions, table creation, FKs, enums, defaults."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.base import Base
from db.models import (
    Directory,
    DirectoryStatus,
    DirectoryHint,
    EnrichmentRun,
    EnrichmentStatus,
    EnrichmentTrigger,
    FileRecord,
    FileStatus,
    Metadata,
    MetadataSource,
    ProcessingLog,
    ProcessingLogLevel,
    ProcessingStep,
    ScanJob,
    ScanJobStatus,
)


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


class TestModelImports:
    def test_all_seven_tables_registered(self):
        names = {t.name for t in Base.metadata.sorted_tables}
        expected = {
            "directories",
            "directory_hints",
            "file_records",
            "enrichment_runs",
            "metadata",
            "processing_logs",
            "scan_jobs",
        }
        assert expected <= names

    def test_enum_values_match_spec(self):
        assert {e.value for e in FileStatus} == {
            "pending",
            "reading",
            "read",
            "ai_queued",
            "analyze_queued",
            "enriching",
            "enriched",
            "accepted",
            "rejected",
            "failed",
            "missing",
        }
        assert {e.value for e in EnrichmentTrigger} == {
            "scan",
            "user_file",
            "retry",
        }
        assert {e.value for e in EnrichmentStatus} == {
            "running",
            "done",
            "failed",
            "cancelled",
        }
        assert {e.value for e in MetadataSource} == {"file", "ai", "accepted", "manual"}
        assert {e.value for e in ProcessingStep} == {
            "scan_discover",
            "scan_rehash",
            "read_metadata",
            "summarize_dir",
            "ai_enrich",
            "write_back",
            "move_or_rename",
        }
        assert {e.value for e in ProcessingLogLevel} == {"info", "warn", "error"}
        assert {e.value for e in DirectoryStatus} == {"active", "missing"}
        assert {e.value for e in ScanJobStatus} == {
            "pending",
            "running",
            "done",
            "failed",
            "cancelled",
        }


class TestDirectorySchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("directories")}
        assert {
            "id",
            "path",
            "name",
            "parent_id",
            "depth",
            "status",
            "file_count",
            "last_scanned_at",
            "discovered_at",
        } <= cols

    def test_status_default_active(self, session):
        d = Directory(path="/lib-default", name="lib-default", depth=0)
        session.add(d)
        session.commit()
        session.refresh(d)
        assert d.status == DirectoryStatus.active

    def test_status_enum_assignment(self, session):
        d = Directory(path="/lib-missing", name="lib-missing", depth=0, status=DirectoryStatus.missing)
        session.add(d)
        session.commit()
        session.refresh(d)
        assert d.status is DirectoryStatus.missing

    def test_path_is_unique(self, engine):
        uniques = inspect(engine).get_unique_constraints("directories")
        unique_cols = {tuple(u["column_names"]) for u in uniques}
        indexed = {tuple(i["column_names"]) for i in inspect(engine).get_indexes("directories") if i["unique"]}
        assert ("path",) in unique_cols or ("path",) in indexed

    def test_parent_self_fk(self, engine):
        fks = inspect(engine).get_foreign_keys("directories")
        targets = {(fk["referred_table"], tuple(fk["constrained_columns"])) for fk in fks}
        assert ("directories", ("parent_id",)) in targets

    def test_self_referential_relationship(self, session):
        root = Directory(path="/lib", name="lib", depth=0)
        child = Directory(path="/lib/a", name="a", depth=1, parent=root)
        session.add_all([root, child])
        session.commit()

        session.refresh(root)
        assert child.parent is root
        assert child in root.children


class TestDirectoryHintSchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("directory_hints")}
        assert {
            "id",
            "directory_id",
            "is_current",
            "data",
            "schema_version",
            "ai_model",
            "prompt_version",
            "created_at",
        } <= cols

    def test_fk_to_directories(self, engine):
        fks = inspect(engine).get_foreign_keys("directory_hints")
        targets = {(fk["referred_table"], tuple(fk["constrained_columns"])) for fk in fks}
        assert ("directories", ("directory_id",)) in targets

    def test_persist_and_traverse(self, session):
        d = Directory(path="/x", name="x", depth=0)
        session.add(d)
        session.flush()
        hint = DirectoryHint(
            directory_id=d.id,
            data={"genre": "scifi", "series": "Dune"},
            ai_model="gpt-4o-mini",
            prompt_version="v1",
        )
        session.add(hint)
        session.commit()
        session.refresh(d)
        assert hint in d.hints
        assert hint.is_current is True
        assert hint.schema_version == "1"
        assert hint.data["genre"] == "scifi"


class TestFileRecordSchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("file_records")}
        assert {
            "id",
            "directory_id",
            "filename",
            "extension",
            "format",
            "sort_order",
            "size",
            "hash",
            "file_modified_at",
            "status",
            "error_message",
            "discovered_at",
            "updated_at",
        } <= cols

    def test_unique_directory_id_filename(self, session):
        d = Directory(path="/d", name="d", depth=0)
        session.add(d)
        session.flush()
        f1 = FileRecord(directory_id=d.id, filename="book.epub")
        session.add(f1)
        session.commit()

        f2 = FileRecord(directory_id=d.id, filename="book.epub")
        session.add(f2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_status_default_pending(self, session):
        d = Directory(path="/d2", name="d2", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="x.epub")
        session.add(f)
        session.commit()
        session.refresh(f)
        assert f.status == FileStatus.pending

    def test_status_enum_assignment(self, session):
        d = Directory(path="/d3", name="d3", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="y.epub", status=FileStatus.enriched)
        session.add(f)
        session.commit()
        session.refresh(f)
        assert f.status is FileStatus.enriched

    @pytest.mark.parametrize(
        "status",
        [FileStatus.read, FileStatus.analyze_queued, FileStatus.missing],
    )
    def test_new_lifecycle_statuses_assignable(self, session, status):
        d = Directory(path=f"/d-{status.value}", name=status.value, depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename=f"{status.value}.epub", status=status)
        session.add(f)
        session.commit()
        session.refresh(f)
        assert f.status is status


class TestEnrichmentRunSchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("enrichment_runs")}
        assert {
            "id",
            "directory_id",
            "directory_hint_id",
            "trigger",
            "status",
            "ai_model",
            "prompt_version",
            "file_count",
            "success_count",
            "failure_count",
            "cost_usd",
            "started_at",
            "finished_at",
            "error_message",
        } <= cols

    def test_nullable_foreign_keys(self, session):
        run = EnrichmentRun(trigger=EnrichmentTrigger.user_file)
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.directory_id is None
        assert run.directory_hint_id is None
        assert run.status is EnrichmentStatus.running

    def test_counters_default_zero(self, session):
        run = EnrichmentRun(trigger=EnrichmentTrigger.scan)
        session.add(run)
        session.commit()
        session.refresh(run)
        assert run.file_count == 0
        assert run.success_count == 0
        assert run.failure_count == 0


class TestMetadataSchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("metadata")}
        assert {
            "id",
            "file_id",
            "source",
            "enrichment_run_id",
            "is_current",
            "title",
            "subtitle",
            "language",
            "series",
            "series_index",
            "series_total",
            "publisher",
            "isbn13",
            "isbn10",
            "asin",
            "published",
            "year",
            "confidence",
            "data",
            "schema_version",
            "created_at",
        } <= cols

    def test_data_required(self, session):
        d = Directory(path="/m", name="m", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="m.epub")
        session.add(f)
        session.flush()

        m = Metadata(file_id=f.id, source=MetadataSource.file)
        session.add(m)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

    def test_persist_with_scalars_and_json(self, session):
        d = Directory(path="/m2", name="m2", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="m2.epub")
        session.add(f)
        session.flush()

        m = Metadata(
            file_id=f.id,
            source=MetadataSource.ai,
            title="Dune",
            language="en",
            series="Dune",
            series_index=1,
            isbn13="9780441013593",
            data={"authors": ["Frank Herbert"], "tags": ["scifi"]},
        )
        session.add(m)
        session.commit()
        session.refresh(m)
        assert m.title == "Dune"
        assert m.is_current is True
        assert m.schema_version == "1"
        assert m.data["authors"] == ["Frank Herbert"]


class TestProcessingLogSchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("processing_logs")}
        assert {
            "id",
            "file_id",
            "enrichment_run_id",
            "step",
            "level",
            "message",
            "details",
            "duration_ms",
            "created_at",
        } <= cols

    def test_default_level_info(self, session):
        d = Directory(path="/p", name="p", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="p.epub")
        session.add(f)
        session.flush()

        log = ProcessingLog(file_id=f.id, step=ProcessingStep.scan_discover, message="found")
        session.add(log)
        session.commit()
        session.refresh(log)
        assert log.level is ProcessingLogLevel.info


class TestScanJobSchema:
    def test_columns_present(self, engine):
        cols = {c["name"] for c in inspect(engine).get_columns("scan_jobs")}
        assert {
            "id",
            "root_directory_id",
            "root_path",
            "status",
            "files_discovered",
            "files_processed",
            "current_file_id",
            "started_at",
            "finished_at",
            "error_message",
            "created_at",
        } <= cols

    def test_default_status_pending(self, session):
        job = ScanJob(root_path="/data/new_books")
        session.add(job)
        session.commit()
        session.refresh(job)
        assert job.status is ScanJobStatus.pending
        assert job.files_discovered == 0
        assert job.files_processed == 0


class TestCascadeRelationships:
    def test_directory_cascades_to_files_and_hints(self, session):
        d = Directory(path="/c", name="c", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="c.epub")
        h = DirectoryHint(directory_id=d.id, data={"x": 1})
        session.add_all([f, h])
        session.commit()

        session.delete(d)
        session.commit()

        assert session.query(FileRecord).count() == 0
        assert session.query(DirectoryHint).count() == 0

    def test_file_cascades_to_metadata_and_logs(self, session):
        d = Directory(path="/c2", name="c2", depth=0)
        session.add(d)
        session.flush()
        f = FileRecord(directory_id=d.id, filename="c2.epub")
        session.add(f)
        session.flush()

        m = Metadata(file_id=f.id, source=MetadataSource.file, data={"k": "v"})
        log = ProcessingLog(file_id=f.id, step=ProcessingStep.read_metadata)
        session.add_all([m, log])
        session.commit()

        session.delete(f)
        session.commit()

        assert session.query(Metadata).count() == 0
        assert session.query(ProcessingLog).count() == 0
