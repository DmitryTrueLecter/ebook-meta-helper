"""Unit tests for app.pipeline.process_file — status transitions, log writes, error routing."""

from __future__ import annotations

from typing import Optional
from unittest.mock import patch

import pytest

from app.models.book import BookRecord
from app.pipeline.process_file import process_file
from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentRun, EnrichmentTrigger
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import (
    ProcessingLog,
    ProcessingLogLevel,
    ProcessingStep,
)


# ---------- helpers ----------


def _make_record(path: str = "/lib/book.fb2", title: str = "Original Title") -> BookRecord:
    return BookRecord(
        path=path,
        original_filename="book.fb2",
        extension="fb2",
        directories=["lib"],
        title=title,
        authors=["Author Original"],
    )


def _seed_directory_file_run(session) -> tuple[int, int]:
    directory = Directory(path="/lib", name="lib", depth=0)
    session.add(directory)
    session.flush()

    file_record = FileRecord(directory_id=directory.id, filename="book.fb2")
    session.add(file_record)

    run = EnrichmentRun(
        directory_id=directory.id, trigger=EnrichmentTrigger.scan
    )
    session.add(run)
    session.flush()
    session.commit()

    return file_record.id, run.id


def _read_returns(extra_title: str = "From File"):
    def _impl(record: BookRecord) -> BookRecord:
        record.title = extra_title
        record.subtitle = "Subtitle From File"
        record.year = 2010
        return record

    return _impl


def _enrich_returns(extra_title: str = "AI Title"):
    def _impl(record: BookRecord, provider_name: str, hint: Optional[dict] = None) -> BookRecord:
        record.title = extra_title
        record.authors = ["AI Author"]
        record.language = "en"
        record.source = "ai"
        record.confidence = 0.9
        return record

    return _impl


# ---------- success paths ----------


class TestHappyPath:
    def test_status_progresses_pending_to_enriched(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch(
            "app.pipeline.process_file.enrich", side_effect=_enrich_returns()
        ):
            result = process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        assert result.success is True
        assert result.errors == []

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.enriched
        assert file_record.error_message is None

    def test_writes_two_metadata_rows_file_then_ai(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata",
            side_effect=_read_returns("From File"),
        ), patch(
            "app.pipeline.process_file.enrich",
            side_effect=_enrich_returns("AI Title"),
        ):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        rows = (
            session.query(Metadata)
            .filter(Metadata.file_id == file_id)
            .order_by(Metadata.id)
            .all()
        )
        assert [r.source for r in rows] == [MetadataSource.file, MetadataSource.ai]
        assert rows[0].title == "From File"
        assert rows[1].title == "AI Title"
        # AI row carries the enrichment_run_id, file row does not
        assert rows[0].enrichment_run_id is None
        assert rows[1].enrichment_run_id == run_id

    def test_writes_two_info_log_entries(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch(
            "app.pipeline.process_file.enrich", side_effect=_enrich_returns()
        ):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        logs = (
            session.query(ProcessingLog)
            .filter(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.id)
            .all()
        )
        assert [(log.step, log.level) for log in logs] == [
            (ProcessingStep.read_metadata, ProcessingLogLevel.info),
            (ProcessingStep.ai_enrich, ProcessingLogLevel.info),
        ]
        assert all(log.enrichment_run_id == run_id for log in logs)

    def test_directory_hint_is_threaded_to_enrich(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")
        captured: dict = {}

        def _spy_enrich(record, provider_name, hint=None):
            captured["hint"] = hint
            captured["provider_name"] = provider_name
            record.source = "ai"
            return record

        hint = {"series": "Ересь Хоруса", "universe": "Warhammer 40k"}

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch("app.pipeline.process_file.enrich", side_effect=_spy_enrich):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=hint,
                session=session,
            )

        assert captured["hint"] == hint
        assert captured["provider_name"] == "dummy"


# ---------- read-step failure ----------


class TestReadStepFailure:
    def test_read_metadata_exception_routes_to_failed(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata",
            side_effect=RuntimeError("FB2 parse error"),
        ), patch("app.pipeline.process_file.enrich") as enrich_mock:
            result = process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        assert result.success is False
        assert result.errors == ["read_metadata: FB2 parse error"]

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.failed
        assert file_record.error_message == "read_metadata: FB2 parse error"

        # enrich must never be called once reading fails
        enrich_mock.assert_not_called()

    def test_read_failure_writes_error_log_only(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata",
            side_effect=RuntimeError("FB2 parse error"),
        ):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        logs = (
            session.query(ProcessingLog)
            .filter(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.id)
            .all()
        )
        assert len(logs) == 1
        assert logs[0].step == ProcessingStep.read_metadata
        assert logs[0].level == ProcessingLogLevel.error
        assert "FB2 parse error" in (logs[0].message or "")

        # no metadata rows persisted on a step-1 failure
        rows = session.query(Metadata).filter(Metadata.file_id == file_id).all()
        assert rows == []


# ---------- enrich-step failure ----------


class TestEnrichStepFailure:
    def test_enrich_exception_routes_to_failed_keeping_file_metadata(
        self, session, monkeypatch
    ):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch(
            "app.pipeline.process_file.enrich",
            side_effect=ConnectionError("provider timeout"),
        ):
            result = process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        assert result.success is False
        assert result.errors == ["ai_enrich: provider timeout"]

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.failed
        assert file_record.error_message == "ai_enrich: provider timeout"

        # Step-1 metadata persisted; step-2 did not.
        sources = [
            row.source
            for row in session.query(Metadata).filter(Metadata.file_id == file_id)
        ]
        assert sources == [MetadataSource.file]

    def test_enrich_failure_writes_two_logs_info_then_error(
        self, session, monkeypatch
    ):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch(
            "app.pipeline.process_file.enrich",
            side_effect=ConnectionError("provider timeout"),
        ):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        logs = (
            session.query(ProcessingLog)
            .filter(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.id)
            .all()
        )
        assert [(log.step, log.level) for log in logs] == [
            (ProcessingStep.read_metadata, ProcessingLogLevel.info),
            (ProcessingStep.ai_enrich, ProcessingLogLevel.error),
        ]

    def test_missing_ai_provider_env_fails_enrich_step(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.delenv("AI_PROVIDER", raising=False)

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch("app.pipeline.process_file.enrich") as enrich_mock:
            result = process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        assert result.success is False
        assert result.errors == ["ai_enrich: AI_PROVIDER is not set"]
        # enrich must not be called when env var is missing
        enrich_mock.assert_not_called()

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.failed


# ---------- transition-level invariants ----------


class TestStatusInvariants:
    def test_status_transitions_in_order(self, session, monkeypatch):
        """Each phase advances status through the documented edges."""
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        observed: list[FileStatus] = []

        original_read = _read_returns()
        original_enrich = _enrich_returns()

        def _watch_read(record):
            observed.append(session.get(FileRecord, file_id).status)
            return original_read(record)

        def _watch_enrich(record, provider_name, hint=None):
            observed.append(session.get(FileRecord, file_id).status)
            return original_enrich(record, provider_name, hint)

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_watch_read
        ), patch(
            "app.pipeline.process_file.enrich", side_effect=_watch_enrich
        ):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        # When read_metadata runs, status is `reading`.
        # When enrich runs, status is `enriching`.
        assert observed == [FileStatus.reading, FileStatus.enriching]
        assert session.get(FileRecord, file_id).status == FileStatus.enriched


# ---------- signature ----------


class TestSignature:
    def test_keyword_arguments_required(self, session, monkeypatch):
        """All five params are part of the public contract; calling out-of-order
        with kwargs (the documented usage) is supported."""
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch(
            "app.pipeline.process_file.enrich", side_effect=_enrich_returns()
        ):
            result = process_file(
                directory_hint={"k": "v"},
                session=session,
                file_id=file_id,
                enrichment_run_id=run_id,
                record=_make_record(),
            )

        assert result.success is True

    def test_directory_hint_none_is_accepted(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")
        captured: dict = {}

        def _spy_enrich(record, provider_name, hint=None):
            captured["hint"] = hint
            record.source = "ai"
            return record

        with patch(
            "app.pipeline.process_file.read_metadata", side_effect=_read_returns()
        ), patch("app.pipeline.process_file.enrich", side_effect=_spy_enrich):
            process_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                directory_hint=None,
                session=session,
            )

        assert captured["hint"] is None
