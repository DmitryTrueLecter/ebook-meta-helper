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
            # discover: find → read metadata (no AI)
            (FileStatus.pending, FileStatus.reading),
            (FileStatus.reading, FileStatus.read),
            # explicit per-file Analyze queues onto the durable marker
            (FileStatus.read, FileStatus.analyze_queued),
            (FileStatus.enriched, FileStatus.analyze_queued),
            (FileStatus.accepted, FileStatus.analyze_queued),
            (FileStatus.rejected, FileStatus.analyze_queued),
            (FileStatus.failed, FileStatus.analyze_queued),
            # drain claims the durable marker
            (FileStatus.analyze_queued, FileStatus.reading),
            (FileStatus.analyze_queued, FileStatus.enriching),
            (FileStatus.analyze_queued, FileStatus.failed),
            # AI enrich tail
            (FileStatus.enriching, FileStatus.enriched),
            (FileStatus.enriched, FileStatus.accepted),
            (FileStatus.enriched, FileStatus.rejected),
            # discover marks files gone, and recovers them on reappearance
            (FileStatus.pending, FileStatus.missing),
            (FileStatus.read, FileStatus.missing),
            (FileStatus.enriched, FileStatus.missing),
            (FileStatus.failed, FileStatus.missing),
            (FileStatus.missing, FileStatus.read),
            # discover re-reads a changed `read` file, and reads a reappeared `missing` one
            (FileStatus.read, FileStatus.reading),
            (FileStatus.missing, FileStatus.reading),
            # legacy transient path retained until DMI-124/125 strip the callers
            (FileStatus.reading, FileStatus.ai_queued),
            (FileStatus.ai_queued, FileStatus.enriching),
        ],
    )
    def test_allowed_moves(self, src, dst):
        assert file_repo.transition(src, dst) is True

    @pytest.mark.parametrize(
        ("src", "dst"),
        [
            (FileStatus.pending, FileStatus.enriched),
            (FileStatus.pending, FileStatus.accepted),
            (FileStatus.read, FileStatus.accepted),
            (FileStatus.analyze_queued, FileStatus.accepted),
            (FileStatus.enriching, FileStatus.accepted),
            (FileStatus.accepted, FileStatus.rejected),
            (FileStatus.rejected, FileStatus.accepted),
            (FileStatus.accepted, FileStatus.pending),
            # accepted/rejected files moved to BOOKS_READY — discover must not mark them missing
            (FileStatus.accepted, FileStatus.missing),
            (FileStatus.rejected, FileStatus.missing),
            # in-flight rows are not part of the missing predicate
            (FileStatus.reading, FileStatus.missing),
            (FileStatus.enriching, FileStatus.missing),
            # missing recovery lands on read, never straight into a terminal/queued state
            (FileStatus.missing, FileStatus.accepted),
            (FileStatus.missing, FileStatus.analyze_queued),
        ],
    )
    def test_forbidden_moves(self, src, dst):
        assert file_repo.transition(src, dst) is False

    def test_failed_reachable_from_every_non_terminal(self):
        for src in (
            FileStatus.pending,
            FileStatus.reading,
            FileStatus.read,
            FileStatus.ai_queued,
            FileStatus.analyze_queued,
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


class TestResetStalledToAnalyzeQueued:
    """Crash-recovery reset bypasses the state machine on purpose — it re-queues
    in-flight rows onto the durable marker, leaving durable/terminal rows untouched."""

    def test_resets_reading_ai_queued_enriching(self, session):
        d = _new_directory(session)
        rec_reading = FileRecord(directory_id=d.id, filename="r.fb2", status=FileStatus.reading)
        rec_ai = FileRecord(directory_id=d.id, filename="q.fb2", status=FileStatus.ai_queued)
        rec_enr = FileRecord(directory_id=d.id, filename="e.fb2", status=FileStatus.enriching)
        session.add_all([rec_reading, rec_ai, rec_enr])
        session.flush()

        count = file_repo.reset_stalled_to_analyze_queued(session)
        assert count == 3

        for rec in (rec_reading, rec_ai, rec_enr):
            session.refresh(rec)
            assert rec.status == FileStatus.analyze_queued

    def test_durable_analyze_queued_untouched(self, session):
        d = _new_directory(session)
        rec = FileRecord(directory_id=d.id, filename="durable.fb2", status=FileStatus.analyze_queued)
        session.add(rec)
        session.flush()

        count = file_repo.reset_stalled_to_analyze_queued(session)
        assert count == 0
        session.refresh(rec)
        assert rec.status == FileStatus.analyze_queued

    def test_leaves_terminal_resting_alone(self, session):
        d = _new_directory(session)
        rec_pending = FileRecord(directory_id=d.id, filename="p.fb2", status=FileStatus.pending)
        rec_read = FileRecord(directory_id=d.id, filename="rd.fb2", status=FileStatus.read)
        rec_enriched = FileRecord(directory_id=d.id, filename="x.fb2", status=FileStatus.enriched)
        rec_failed = FileRecord(directory_id=d.id, filename="f.fb2", status=FileStatus.failed)
        rec_accepted = FileRecord(directory_id=d.id, filename="a.fb2", status=FileStatus.accepted)
        rec_rejected = FileRecord(directory_id=d.id, filename="j.fb2", status=FileStatus.rejected)
        rec_missing = FileRecord(directory_id=d.id, filename="m.fb2", status=FileStatus.missing)
        session.add_all(
            [rec_pending, rec_read, rec_enriched, rec_failed, rec_accepted, rec_rejected, rec_missing]
        )
        session.flush()

        count = file_repo.reset_stalled_to_analyze_queued(session)
        assert count == 0

        for rec, expected in (
            (rec_pending, FileStatus.pending),
            (rec_read, FileStatus.read),
            (rec_enriched, FileStatus.enriched),
            (rec_failed, FileStatus.failed),
            (rec_accepted, FileStatus.accepted),
            (rec_rejected, FileStatus.rejected),
            (rec_missing, FileStatus.missing),
        ):
            session.refresh(rec)
            assert rec.status == expected

    def test_clears_error_message_on_reset(self, session):
        d = _new_directory(session)
        rec = FileRecord(
            directory_id=d.id,
            filename="r.fb2",
            status=FileStatus.enriching,
            error_message="from prior crash",
        )
        session.add(rec)
        session.flush()

        file_repo.reset_stalled_to_analyze_queued(session)
        session.refresh(rec)
        assert rec.error_message is None


class TestListDirectoriesWithPending:
    def test_returns_only_directories_with_pending_files(self, session):
        d1 = _new_directory(session, path="/d1")
        d2 = _new_directory(session, path="/d2")
        d3 = _new_directory(session, path="/d3")  # has no files at all

        session.add_all([
            FileRecord(directory_id=d1.id, filename="a.fb2", status=FileStatus.pending),
            FileRecord(directory_id=d1.id, filename="b.fb2", status=FileStatus.enriched),
            FileRecord(directory_id=d2.id, filename="c.fb2", status=FileStatus.pending),
        ])
        session.flush()

        dirs = file_repo.list_directories_with_pending(session)
        ids = {d.id for d in dirs}
        assert ids == {d1.id, d2.id}

    def test_directory_with_no_pending_excluded(self, session):
        d = _new_directory(session)
        session.add(FileRecord(directory_id=d.id, filename="done.fb2", status=FileStatus.enriched))
        session.flush()

        assert file_repo.list_directories_with_pending(session) == []

    def test_deduplicates_directories_with_multiple_pending(self, session):
        d = _new_directory(session)
        session.add_all([
            FileRecord(directory_id=d.id, filename="a.fb2", status=FileStatus.pending),
            FileRecord(directory_id=d.id, filename="b.fb2", status=FileStatus.pending),
            FileRecord(directory_id=d.id, filename="c.fb2", status=FileStatus.pending),
        ])
        session.flush()

        dirs = file_repo.list_directories_with_pending(session)
        assert [d.id for d in dirs] == [d.id]


class TestCountByStatus:
    def test_counts_each_status_independently(self, session):
        d = _new_directory(session)
        session.add_all([
            FileRecord(directory_id=d.id, filename="a.fb2", status=FileStatus.pending),
            FileRecord(directory_id=d.id, filename="b.fb2", status=FileStatus.pending),
            FileRecord(directory_id=d.id, filename="c.fb2", status=FileStatus.enriched),
        ])
        session.flush()

        assert file_repo.count_by_status(session, FileStatus.pending) == 2
        assert file_repo.count_by_status(session, FileStatus.enriched) == 1
        assert file_repo.count_by_status(session, FileStatus.failed) == 0


class TestMarkMissingUnderRoot:
    def _file(self, session, directory, filename, status):
        record = FileRecord(directory_id=directory.id, filename=filename, status=status)
        session.add(record)
        session.flush()
        return record

    def test_absent_reconcilable_file_marked_missing(self, session):
        d = _new_directory(session, "/books/sci")
        present = self._file(session, d, "here.fb2", FileStatus.read)
        gone = self._file(session, d, "gone.fb2", FileStatus.read)

        marked = file_repo.mark_missing_under_root(
            session, "/books/sci", {"/books/sci/here.fb2"}
        )
        session.flush()

        assert marked == 1
        assert session.get(FileRecord, gone.id).status == FileStatus.missing
        assert session.get(FileRecord, present.id).status == FileStatus.read

    def test_accepted_and_in_flight_never_marked(self, session):
        d = _new_directory(session, "/books/sci")
        accepted = self._file(session, d, "accepted.fb2", FileStatus.accepted)
        rejected = self._file(session, d, "rejected.fb2", FileStatus.rejected)
        reading = self._file(session, d, "reading.fb2", FileStatus.reading)

        marked = file_repo.mark_missing_under_root(session, "/books/sci", set())
        session.flush()

        assert marked == 0
        assert session.get(FileRecord, accepted.id).status == FileStatus.accepted
        assert session.get(FileRecord, rejected.id).status == FileStatus.rejected
        assert session.get(FileRecord, reading.id).status == FileStatus.reading

    def test_sibling_prefix_directory_not_cross_matched(self, session):
        sci = _new_directory(session, "/books/sci")
        science = _new_directory(session, "/books/science")
        in_scope = self._file(session, sci, "a.fb2", FileStatus.read)
        sibling = self._file(session, science, "b.fb2", FileStatus.read)

        # Reconcile only the /books/sci subtree with an empty present-set.
        marked = file_repo.mark_missing_under_root(session, "/books/sci", set())
        session.flush()

        assert marked == 1
        assert session.get(FileRecord, in_scope.id).status == FileStatus.missing
        # /books/science is a sibling prefix — it must NOT be touched.
        assert session.get(FileRecord, sibling.id).status == FileStatus.read

    def test_underscore_in_root_not_treated_as_wildcard(self, session):
        """A literal `_` in the root path must not match arbitrary chars via LIKE."""
        scoped_child = _new_directory(session, "/books/sci_fi/sub")
        decoy_child = _new_directory(session, "/books/sciXfi/sub")
        in_scope = self._file(session, scoped_child, "a.fb2", FileStatus.read)
        out_of_scope = self._file(session, decoy_child, "b.fb2", FileStatus.read)

        # Unescaped, `/books/sci_fi/%` would also match `/books/sciXfi/sub` (`_` = any char).
        marked = file_repo.mark_missing_under_root(session, "/books/sci_fi", set())
        session.flush()

        assert marked == 1
        assert session.get(FileRecord, in_scope.id).status == FileStatus.missing
        assert session.get(FileRecord, out_of_scope.id).status == FileStatus.read

    def test_enriched_and_failed_are_reconcilable(self, session):
        d = _new_directory(session, "/books/sci")
        enriched = self._file(session, d, "enriched.fb2", FileStatus.enriched)
        failed = self._file(session, d, "failed.fb2", FileStatus.failed)

        marked = file_repo.mark_missing_under_root(session, "/books/sci", set())
        session.flush()

        assert marked == 2
        assert session.get(FileRecord, enriched.id).status == FileStatus.missing
        assert session.get(FileRecord, failed.id).status == FileStatus.missing
