"""Unit tests for db.repos.log_repo."""

from __future__ import annotations

from db.models.directory import Directory
from db.models.file_record import FileRecord
from db.models.processing_log import ProcessingLogLevel, ProcessingStep
from db.repos import log_repo
from db.repos.log_repo import LogEntry


def _new_file(session) -> FileRecord:
    d = Directory(path="/lib", name="lib", depth=0)
    session.add(d)
    session.flush()
    f = FileRecord(directory_id=d.id, filename="book.epub")
    session.add(f)
    session.flush()
    return f


class TestWrite:
    def test_minimum_fields(self, session):
        f = _new_file(session)
        log = log_repo.write(
            session,
            LogEntry(file_id=f.id, step=ProcessingStep.scan_discover),
        )
        assert log.id is not None
        assert log.step == ProcessingStep.scan_discover
        assert log.level == ProcessingLogLevel.info
        assert log.message is None

    def test_full_fields(self, session):
        f = _new_file(session)
        log = log_repo.write(
            session,
            LogEntry(
                file_id=f.id,
                step=ProcessingStep.ai_enrich,
                level=ProcessingLogLevel.error,
                message="OpenAI 500",
                details={"http_status": 500, "retry": 3},
                duration_ms=12345,
            ),
        )
        assert log.level == ProcessingLogLevel.error
        assert log.message == "OpenAI 500"
        assert log.details["http_status"] == 500
        assert log.duration_ms == 12345


class TestGetForFile:
    def test_newest_first(self, session):
        f = _new_file(session)
        log_repo.write(
            session,
            LogEntry(file_id=f.id, step=ProcessingStep.scan_discover, message="1"),
        )
        log_repo.write(
            session,
            LogEntry(file_id=f.id, step=ProcessingStep.read_metadata, message="2"),
        )
        log_repo.write(
            session,
            LogEntry(file_id=f.id, step=ProcessingStep.ai_enrich, message="3"),
        )

        rows = log_repo.get_for_file(session, f.id)
        assert [r.message for r in rows] == ["3", "2", "1"]

    def test_respects_limit(self, session):
        f = _new_file(session)
        for i in range(10):
            log_repo.write(
                session,
                LogEntry(file_id=f.id, step=ProcessingStep.scan_discover, message=str(i)),
            )
        assert len(log_repo.get_for_file(session, f.id, limit=3)) == 3

    def test_scoped_to_file(self, session):
        f1 = _new_file(session)
        d = session.query(Directory).first()
        f2 = FileRecord(directory_id=d.id, filename="other.epub")
        session.add(f2)
        session.flush()

        log_repo.write(
            session,
            LogEntry(file_id=f1.id, step=ProcessingStep.scan_discover, message="f1"),
        )
        log_repo.write(
            session,
            LogEntry(file_id=f2.id, step=ProcessingStep.scan_discover, message="f2"),
        )

        rows = log_repo.get_for_file(session, f1.id)
        assert [r.message for r in rows] == ["f1"]


class TestMessageTruncation:
    """The message column is String(1024). An over-long error message (e.g. a wrapped
    DataError with a full SQL statement) must be truncated before insert — a too-long
    message previously raised mid-cycle and aborted the entire discover pass."""

    def test_overlong_message_truncated_to_column_limit(self, session):
        f = _new_file(session)
        log = log_repo.write(
            session,
            LogEntry(
                file_id=f.id,
                step=ProcessingStep.read_metadata,
                level=ProcessingLogLevel.error,
                message="x" * 5000,
            ),
        )
        assert log.message is not None
        assert len(log.message) <= 1024

    def test_short_message_unchanged(self, session):
        f = _new_file(session)
        log = log_repo.write(
            session,
            LogEntry(file_id=f.id, step=ProcessingStep.read_metadata, message="ok"),
        )
        assert log.message == "ok"
