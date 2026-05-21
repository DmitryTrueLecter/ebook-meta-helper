"""Unit tests for db.repos.file_repo — get_or_create, state machine, queries."""

from __future__ import annotations

import pytest

from db.models.directory import Directory
from db.models.file_record import FileRecord, FileStatus
from db.repos import file_repo
from db.repos.file_repo import FileAttrs, InvalidStatusTransition


def _new_directory(session, path: str = "/lib") -> Directory:
    d = Directory(path=path, name=path.rsplit("/", 1)[-1] or "root", depth=0)
    session.add(d)
    session.flush()
    return d


class TestTransitionPredicate:
    @pytest.mark.parametrize(
        ("src", "dst"),
        [
            (FileStatus.pending, FileStatus.reading),
            (FileStatus.reading, FileStatus.ai_queued),
            (FileStatus.reading, FileStatus.enriched),
            (FileStatus.ai_queued, FileStatus.enriching),
            (FileStatus.enriching, FileStatus.enriched),
            (FileStatus.enriched, FileStatus.accepted),
            (FileStatus.enriched, FileStatus.rejected),
            (FileStatus.accepted, FileStatus.ai_queued),
            (FileStatus.rejected, FileStatus.ai_queued),
            (FileStatus.failed, FileStatus.pending),
            (FileStatus.failed, FileStatus.ai_queued),
        ],
    )
    def test_allowed_moves(self, src, dst):
        assert file_repo.transition(src, dst) is True

    @pytest.mark.parametrize(
        ("src", "dst"),
        [
            (FileStatus.pending, FileStatus.enriched),
            (FileStatus.pending, FileStatus.accepted),
            (FileStatus.reading, FileStatus.accepted),
            (FileStatus.ai_queued, FileStatus.accepted),
            (FileStatus.enriching, FileStatus.accepted),
            (FileStatus.accepted, FileStatus.rejected),
            (FileStatus.rejected, FileStatus.accepted),
            (FileStatus.accepted, FileStatus.pending),
        ],
    )
    def test_forbidden_moves(self, src, dst):
        assert file_repo.transition(src, dst) is False

    def test_failed_reachable_from_every_non_terminal(self):
        for src in (
            FileStatus.pending,
            FileStatus.reading,
            FileStatus.ai_queued,
            FileStatus.enriching,
            FileStatus.enriched,
        ):
            assert file_repo.transition(src, FileStatus.failed) is True

    def test_self_loop_allowed(self):
        # No-op assignments must not raise; callers may set status to itself.
        for s in FileStatus:
            assert file_repo.transition(s, s) is True


class TestGetOrCreate:
    def test_creates_with_defaults(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(session, d.id, "book.epub")
        assert f.id is not None
        assert f.filename == "book.epub"
        assert f.status == FileStatus.pending
        assert f.extension is None

    def test_creates_with_attrs(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(
            session,
            d.id,
            "book.epub",
            FileAttrs(extension="epub", format="EPUB 3.0", size=1024, hash="a" * 64),
        )
        assert f.extension == "epub"
        assert f.format == "EPUB 3.0"
        assert f.size == 1024
        assert f.hash == "a" * 64

    def test_returns_existing(self, session):
        d = _new_directory(session)
        first = file_repo.get_or_create(session, d.id, "book.epub")
        second = file_repo.get_or_create(
            session, d.id, "book.epub", FileAttrs(size=999)
        )
        assert first.id == second.id
        # existing row is returned untouched; size from FileAttrs is ignored
        assert second.size is None


class TestUpdateStatus:
    def test_applies_allowed_move(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(session, d.id, "book.epub")
        updated = file_repo.update_status(session, f.id, FileStatus.reading)
        assert updated.status == FileStatus.reading

    def test_rejects_invalid_move(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(session, d.id, "book.epub")
        with pytest.raises(InvalidStatusTransition) as exc_info:
            file_repo.update_status(session, f.id, FileStatus.accepted)
        assert exc_info.value.from_status == FileStatus.pending
        assert exc_info.value.to_status == FileStatus.accepted
        # state must not have changed
        session.refresh(f)
        assert f.status == FileStatus.pending

    def test_failed_sets_error_message(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(session, d.id, "book.epub")
        file_repo.update_status(
            session, f.id, FileStatus.failed, error_message="parse failed"
        )
        session.refresh(f)
        assert f.status == FileStatus.failed
        assert f.error_message == "parse failed"

    def test_failed_without_message_clears_error(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(session, d.id, "book.epub")
        f.error_message = "previous"
        session.flush()

        file_repo.update_status(session, f.id, FileStatus.failed)
        session.refresh(f)
        assert f.status == FileStatus.failed
        assert f.error_message is None

    def test_non_failed_keeps_error_when_not_supplied(self, session):
        d = _new_directory(session)
        f = file_repo.get_or_create(session, d.id, "book.epub")
        f.status = FileStatus.failed
        f.error_message = "earlier"
        session.flush()

        file_repo.update_status(session, f.id, FileStatus.pending)
        session.refresh(f)
        assert f.status == FileStatus.pending
        # nothing supplied, so the existing message is preserved
        assert f.error_message == "earlier"

    def test_raises_on_missing(self, session):
        with pytest.raises(LookupError):
            file_repo.update_status(session, file_id=999, new_status=FileStatus.reading)


class TestGetByDirectory:
    def test_returns_files_sorted(self, session):
        d = _new_directory(session)
        b = FileRecord(directory_id=d.id, filename="b.epub", sort_order=2.0)
        a = FileRecord(directory_id=d.id, filename="a.epub", sort_order=1.0)
        c = FileRecord(directory_id=d.id, filename="c.epub", sort_order=None)
        session.add_all([b, a, c])
        session.flush()

        rows = file_repo.get_by_directory(session, d.id)
        names = [r.filename for r in rows]
        # NULLs sort last in MySQL ASC and in our chosen ordering; SQLite differs,
        # so we assert only that a and b come out in sort_order ascending.
        assert names.index("a.epub") < names.index("b.epub")
        assert "c.epub" in names

    def test_filters_by_status(self, session):
        d = _new_directory(session)
        keep = file_repo.get_or_create(session, d.id, "keep.epub")
        skip = file_repo.get_or_create(session, d.id, "skip.epub")
        skip.status = FileStatus.enriched
        session.flush()

        rows = file_repo.get_by_directory(session, d.id, status=FileStatus.pending)
        assert [r.id for r in rows] == [keep.id]

    def test_scoped_to_directory(self, session):
        d1 = _new_directory(session, path="/d1")
        d2 = _new_directory(session, path="/d2")
        file_repo.get_or_create(session, d1.id, "x.epub")
        file_repo.get_or_create(session, d2.id, "y.epub")

        rows = file_repo.get_by_directory(session, d1.id)
        assert [r.filename for r in rows] == ["x.epub"]
