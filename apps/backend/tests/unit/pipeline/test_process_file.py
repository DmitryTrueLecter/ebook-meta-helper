"""Unit tests for app.pipeline.process_file.analyze_file — AI-only enrich, status transitions, error routing."""

from __future__ import annotations

from typing import Optional
from unittest.mock import patch

from app.ai.base import AIConfigSnapshot, EnrichOutcome
from app.models.book import BookRecord
from app.pipeline.process_file import analyze_file
from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentRun, EnrichmentTrigger
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import (
    ProcessingLog,
    ProcessingLogLevel,
    ProcessingStep,
)


def _make_record(path: str = "/lib/book.fb2", title: str = "From File") -> BookRecord:
    return BookRecord(
        path=path,
        original_filename="book.fb2",
        extension="fb2",
        directories=["lib"],
        title=title,
        authors=["Author Original"],
        source="file",
    )


def _seed_directory_file_run(session) -> tuple[int, int]:
    """Seed a file already at `reading` — the claim step has run before analyze_file."""
    directory = Directory(path="/lib", name="lib", depth=0)
    session.add(directory)
    session.flush()

    file_record = FileRecord(
        directory_id=directory.id, filename="book.fb2", status=FileStatus.reading
    )
    session.add(file_record)

    run = EnrichmentRun(directory_id=directory.id, trigger=EnrichmentTrigger.user_file)
    session.add(run)
    session.flush()
    session.commit()

    return file_record.id, run.id


def _outcome(record: BookRecord) -> EnrichOutcome:
    return EnrichOutcome(record=record, calls=[], canonical_sequence=0)


def _enrich_returns(extra_title: str = "AI Title"):
    def _impl(
        record: BookRecord,
        provider_name: str,
        config: AIConfigSnapshot,
        directory_hint: Optional[dict] = None,
    ) -> EnrichOutcome:
        record.title = extra_title
        record.authors = ["AI Author"]
        record.language = "en"
        record.source = "ai"
        record.confidence = 0.9
        return _outcome(record)

    return _impl


class TestHappyPath:
    def test_status_progresses_reading_to_enriched(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch("app.pipeline.process_file.enrich", side_effect=_enrich_returns()):
            result = analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        assert result.success is True
        assert result.errors == []

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.enriched
        assert file_record.error_message is None

    def test_writes_one_ai_metadata_row(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch("app.pipeline.process_file.enrich", side_effect=_enrich_returns("AI Title")):
            analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        rows = (
            session.query(Metadata)
            .filter(Metadata.file_id == file_id)
            .order_by(Metadata.id)
            .all()
        )
        # analyze_file does NOT re-read the file — it only writes the AI snapshot.
        assert [r.source for r in rows] == [MetadataSource.ai]
        assert rows[0].title == "AI Title"
        assert rows[0].enrichment_run_id == run_id

    def test_writes_single_ai_enrich_info_log(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch("app.pipeline.process_file.enrich", side_effect=_enrich_returns()):
            analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        logs = (
            session.query(ProcessingLog)
            .filter(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.id)
            .all()
        )
        assert [(log.step, log.level) for log in logs] == [
            (ProcessingStep.ai_enrich, ProcessingLogLevel.info),
        ]
        assert logs[0].enrichment_run_id == run_id

    def test_no_directory_hint_passed_to_enrich(self, session, monkeypatch):
        """Directory-hint dropped: one OpenAI call per file, hint is always None."""
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")
        captured: dict = {}

        def _spy_enrich(record, provider_name, config, directory_hint=None):
            captured["directory_hint"] = directory_hint
            captured["provider_name"] = provider_name
            captured["config"] = config
            record.source = "ai"
            return _outcome(record)

        with patch("app.pipeline.process_file.enrich", side_effect=_spy_enrich):
            analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        assert captured["directory_hint"] is None
        assert captured["provider_name"] == "dummy"
        assert isinstance(captured["config"], AIConfigSnapshot)


class TestEnrichStepFailure:
    def test_enrich_exception_routes_to_failed(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.enrich",
            side_effect=ConnectionError("provider timeout"),
        ):
            result = analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        assert result.success is False
        assert result.errors == ["ai_enrich: provider timeout"]

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.failed
        assert file_record.error_message == "ai_enrich: provider timeout"

        # No AI snapshot persisted on a failed enrich.
        sources = [
            row.source
            for row in session.query(Metadata).filter(Metadata.file_id == file_id)
        ]
        assert sources == []

    def test_enrich_failure_writes_single_error_log(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        with patch(
            "app.pipeline.process_file.enrich",
            side_effect=ConnectionError("provider timeout"),
        ):
            analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        logs = (
            session.query(ProcessingLog)
            .filter(ProcessingLog.file_id == file_id)
            .order_by(ProcessingLog.id)
            .all()
        )
        assert [(log.step, log.level) for log in logs] == [
            (ProcessingStep.ai_enrich, ProcessingLogLevel.error),
        ]

    def test_missing_ai_provider_env_fails_enrich_step(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.delenv("AI_PROVIDER", raising=False)

        with patch("app.pipeline.process_file.enrich") as enrich_mock:
            result = analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        assert result.success is False
        assert result.errors == ["ai_enrich: AI_PROVIDER is not set"]
        enrich_mock.assert_not_called()

        file_record = session.get(FileRecord, file_id)
        assert file_record.status == FileStatus.failed


class TestStatusInvariants:
    def test_enrich_runs_while_enriching(self, session, monkeypatch):
        file_id, run_id = _seed_directory_file_run(session)
        monkeypatch.setenv("AI_PROVIDER", "dummy")

        observed: list[FileStatus] = []
        original_enrich = _enrich_returns()

        def _watch_enrich(record, provider_name, config, directory_hint=None):
            observed.append(session.get(FileRecord, file_id).status)
            return original_enrich(record, provider_name, config, directory_hint)

        with patch("app.pipeline.process_file.enrich", side_effect=_watch_enrich):
            analyze_file(
                record=_make_record(),
                file_id=file_id,
                enrichment_run_id=run_id,
                session=session,
            )

        # The AI call runs only after the row moved to `enriching`.
        assert observed == [FileStatus.enriching]
        assert session.get(FileRecord, file_id).status == FileStatus.enriched
