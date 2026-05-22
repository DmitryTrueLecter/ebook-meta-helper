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


class TestGetById:
    def test_returns_record(self, session):
        d = _new_directory(session)
        created = file_repo.get_or_create(session, d.id, "a.epub")
        assert file_repo.get_by_id(session, created.id) is created

    def test_returns_none_when_missing(self, session):
        assert file_repo.get_by_id(session, 9999) is None


class TestListPaginated:
    def test_returns_first_page_with_total(self, session):
        d = _new_directory(session)
        for i in range(7):
            file_repo.get_or_create(session, d.id, f"f{i}.epub")

        page = file_repo.list_paginated(session, page=1, page_size=3)
        assert page.total == 7
        assert len(page.items) == 3
        assert [r.filename for r in page.items] == ["f0.epub", "f1.epub", "f2.epub"]

    def test_second_page_offsets_correctly(self, session):
        d = _new_directory(session)
        for i in range(7):
            file_repo.get_or_create(session, d.id, f"f{i}.epub")

        page = file_repo.list_paginated(session, page=2, page_size=3)
        assert [r.filename for r in page.items] == ["f3.epub", "f4.epub", "f5.epub"]

    def test_filters_by_directory(self, session):
        d1 = _new_directory(session, path="/d1")
        d2 = _new_directory(session, path="/d2")
        file_repo.get_or_create(session, d1.id, "a.epub")
        file_repo.get_or_create(session, d2.id, "b.epub")

        page = file_repo.list_paginated(session, page=1, page_size=50, directory_id=d2.id)
        assert page.total == 1
        assert [r.filename for r in page.items] == ["b.epub"]

    def test_filters_by_status(self, session):
        d = _new_directory(session)
        keep = file_repo.get_or_create(session, d.id, "k.epub")
        skip = file_repo.get_or_create(session, d.id, "s.epub")
        skip.status = FileStatus.enriched
        session.flush()

        page = file_repo.list_paginated(session, page=1, page_size=10, status=FileStatus.pending)
        assert page.total == 1
        assert [r.id for r in page.items] == [keep.id]

    def test_total_reflects_all_matches_not_page(self, session):
        d = _new_directory(session)
        for i in range(5):
            file_repo.get_or_create(session, d.id, f"f{i}.epub")

        page = file_repo.list_paginated(session, page=1, page_size=2)
        assert page.total == 5
        assert len(page.items) == 2

    def test_page_zero_raises(self, session):
        with pytest.raises(ValueError, match="page must be >= 1"):
            file_repo.list_paginated(session, page=0, page_size=10)

    def test_page_size_zero_raises(self, session):
        with pytest.raises(ValueError, match="page_size must be >= 1"):
            file_repo.list_paginated(session, page=1, page_size=0)

    def test_returns_empty_when_no_matches(self, session):
        page = file_repo.list_paginated(session, page=1, page_size=10)
        assert page.total == 0
        assert page.items == []

    def test_page_beyond_total_returns_empty_items_with_full_total(self, session):
        d = _new_directory(session)
        for i in range(7):
            file_repo.get_or_create(session, d.id, f"f{i}.epub")

        page = file_repo.list_paginated(session, page=100, page_size=3)
        assert page.total == 7
        assert page.items == []
