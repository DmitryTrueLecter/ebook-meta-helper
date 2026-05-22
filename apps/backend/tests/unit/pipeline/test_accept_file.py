"""Unit tests for app.pipeline.accept_file — write-back, rename, move, snapshot, transition."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.metadata.writer.base import WriteResult
from app.pipeline.accept_file import AcceptError, accept_file
from db.base import Base
from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from db.models.metadata import Metadata, MetadataSource
from db.models.processing_log import ProcessingLog
import db.models  # noqa: F401 — register all models with Base.metadata
from db.repos import metadata_repo
from db.repos.metadata_repo import MetadataInput, MetadataScalars


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s
    engine.dispose()


@pytest.fixture
def file_setup(session, tmp_path):
    """Build a Directory + FileRecord with an `ai` metadata snapshot on disk."""
    book_path = tmp_path / "book.epub"
    book_path.write_bytes(b"placeholder")
    directory = Directory(path=str(tmp_path), name=tmp_path.name, depth=0)
    session.add(directory)
    session.flush()
    record = FileRecord(
        directory_id=directory.id,
        filename="book.epub",
        extension="epub",
        format="EPUB",
        status=FileStatus.enriched,
    )
    session.add(record)
    session.flush()
    metadata_repo.create(
        session,
        MetadataInput(
            file_id=record.id,
            source=MetadataSource.ai,
            data={"authors": ["Asimov"], "tags": ["sci-fi"]},
            scalars=MetadataScalars(title="Foundation", language="en"),
        ),
    )
    return record, book_path


@pytest.fixture
def configured_env(monkeypatch, tmp_path):
    target = tmp_path / "ready"
    monkeypatch.setenv("BOOKS_READY_DIR", str(target))
    monkeypatch.setenv("FILENAME_TEMPLATE", "{Title}")
    return target


@pytest.fixture
def stub_write_success(monkeypatch):
    monkeypatch.setattr(
        "app.pipeline.accept_file.write_metadata",
        lambda record: WriteResult(success=True),
    )


class TestAcceptFile:
    def test_writes_metadata_renames_moves_and_snapshots(
        self, session, file_setup, configured_env, stub_write_success
    ):
        record, source_path = file_setup
        target_dir = configured_env

        result = accept_file(session, record.id)

        assert result.file_id == record.id
        assert result.final_path == target_dir / "Foundation.epub"
        assert result.final_path.exists()
        assert not source_path.exists()

    def test_transitions_status_to_accepted(
        self, session, file_setup, configured_env, stub_write_success
    ):
        record, _ = file_setup
        accept_file(session, record.id)
        session.refresh(record)
        assert record.status == FileStatus.accepted

    def test_creates_accepted_metadata_snapshot(
        self, session, file_setup, configured_env, stub_write_success
    ):
        record, _ = file_setup
        accept_file(session, record.id)

        accepted = (
            session.query(Metadata)
            .filter(
                Metadata.file_id == record.id,
                Metadata.source == MetadataSource.accepted,
                Metadata.is_current.is_(True),
            )
            .one()
        )
        assert accepted.title == "Foundation"
        assert accepted.language == "en"

    def test_writes_processing_log_entry(
        self, session, file_setup, configured_env, stub_write_success
    ):
        record, _ = file_setup
        accept_file(session, record.id)
        logs = session.query(ProcessingLog).filter(ProcessingLog.file_id == record.id).all()
        assert len(logs) == 1
        assert logs[0].step.value == "write_back"

    def test_raises_when_file_missing(self, session):
        with pytest.raises(AcceptError, match="not found"):
            accept_file(session, 999)

    def test_raises_when_no_ai_metadata(self, session, tmp_path, configured_env):
        directory = Directory(path=str(tmp_path), name=tmp_path.name, depth=0)
        session.add(directory)
        session.flush()
        record = FileRecord(
            directory_id=directory.id, filename="x.epub", extension="epub",
            status=FileStatus.enriched,
        )
        session.add(record)
        session.flush()

        with pytest.raises(AcceptError, match="no current AI metadata"):
            accept_file(session, record.id)

    def test_raises_when_write_metadata_fails_unrecoverably(
        self, session, file_setup, configured_env, monkeypatch
    ):
        record, _ = file_setup
        monkeypatch.setattr(
            "app.pipeline.accept_file.write_metadata",
            lambda r: WriteResult(success=False, errors=["fb2: no description"]),
        )
        with pytest.raises(AcceptError, match="write_metadata failed"):
            accept_file(session, record.id)

    def test_skipped_write_is_acceptable_when_format_unsupported(
        self, session, file_setup, configured_env, monkeypatch
    ):
        record, _ = file_setup
        monkeypatch.setattr(
            "app.pipeline.accept_file.write_metadata",
            lambda r: WriteResult(success=False, skipped=True),
        )
        result = accept_file(session, record.id)
        assert result.file_id == record.id

    def test_missing_books_ready_dir_raises(
        self, session, file_setup, stub_write_success, monkeypatch
    ):
        record, _ = file_setup
        monkeypatch.delenv("BOOKS_READY_DIR", raising=False)
        monkeypatch.setenv("FILENAME_TEMPLATE", "{Title}")
        with pytest.raises(AcceptError, match="BOOKS_READY_DIR"):
            accept_file(session, record.id)

    def test_missing_filename_template_raises(
        self, session, file_setup, stub_write_success, monkeypatch, tmp_path
    ):
        record, _ = file_setup
        monkeypatch.setenv("BOOKS_READY_DIR", str(tmp_path / "ready"))
        monkeypatch.delenv("FILENAME_TEMPLATE", raising=False)
        with pytest.raises(AcceptError, match="FILENAME_TEMPLATE"):
            accept_file(session, record.id)

    def test_merges_file_and_ai_snapshots_ai_wins(
        self, session, file_setup, configured_env, stub_write_success, monkeypatch
    ):
        record, _ = file_setup
        # add a file-source snapshot with a conflicting title — AI should win
        metadata_repo.create(
            session,
            MetadataInput(
                file_id=record.id,
                source=MetadataSource.file,
                data={"authors": ["Old"]},
                scalars=MetadataScalars(title="Old Title", language="ru"),
            ),
        )
        captured = {}

        def capture(book_record):
            captured["title"] = book_record.title
            captured["language"] = book_record.language
            return WriteResult(success=True)

        monkeypatch.setattr("app.pipeline.accept_file.write_metadata", capture)

        accept_file(session, record.id)
        assert captured["title"] == "Foundation"  # AI title wins
        assert captured["language"] == "en"  # AI language wins
