"""Unit tests for db.repos.directory_repo."""

from __future__ import annotations

import pytest

from db.models.directory import Directory
from db.models.file_record import FileStatus
from db.repos import directory_repo, file_repo
from db.repos.directory_repo import DirectoryInput, DirectoryStats
from db.repos.file_repo import FileAttrs


def _spec(path: str, name: str, parent_id: int | None = None, depth: int = 0) -> DirectoryInput:
    return DirectoryInput(path=path, name=name, parent_id=parent_id, depth=depth)


class TestGetOrCreate:
    def test_creates_when_missing(self, session):
        d = directory_repo.get_or_create(session, _spec("/lib", "lib"))
        assert d.id is not None
        assert d.path == "/lib"
        assert d.name == "lib"
        assert d.depth == 0
        assert d.file_count == 0

    def test_returns_existing_by_path(self, session):
        first = directory_repo.get_or_create(session, _spec("/lib", "lib"))
        second = directory_repo.get_or_create(session, _spec("/lib", "lib-renamed"))
        assert first.id == second.id
        # existing row is returned untouched; the caller does not get "lib-renamed"
        assert second.name == "lib"
        assert session.query(Directory).count() == 1

    def test_links_parent(self, session):
        root = directory_repo.get_or_create(session, _spec("/lib", "lib"))
        child = directory_repo.get_or_create(
            session, _spec("/lib/scifi", "scifi", parent_id=root.id, depth=1)
        )
        assert child.parent_id == root.id
        assert child.depth == 1


class TestUpdateFileCount:
    def test_increments_and_decrements(self, session):
        d = directory_repo.get_or_create(session, _spec("/a", "a"))
        directory_repo.update_file_count(session, d.id, delta=3)
        session.refresh(d)
        assert d.file_count == 3

        directory_repo.update_file_count(session, d.id, delta=-1)
        session.refresh(d)
        assert d.file_count == 2

    def test_raises_on_missing(self, session):
        with pytest.raises(LookupError):
            directory_repo.update_file_count(session, directory_id=999, delta=1)


class TestSetLastScanned:
    def test_sets_timestamp(self, session):
        d = directory_repo.get_or_create(session, _spec("/a", "a"))
        assert d.last_scanned_at is None
        directory_repo.set_last_scanned(session, d.id)
        session.refresh(d)
        assert d.last_scanned_at is not None

    def test_raises_on_missing(self, session):
        with pytest.raises(LookupError):
            directory_repo.set_last_scanned(session, directory_id=999)


class TestGetTree:
    def test_returns_roots_first_and_eager_loads_children(self, session):
        root = directory_repo.get_or_create(session, _spec("/lib", "lib"))
        child_a = directory_repo.get_or_create(
            session, _spec("/lib/a", "a", parent_id=root.id, depth=1)
        )
        directory_repo.get_or_create(
            session, _spec("/lib/b", "b", parent_id=root.id, depth=1)
        )
        directory_repo.get_or_create(
            session, _spec("/lib/a/inner", "inner", parent_id=child_a.id, depth=2)
        )

        tree = directory_repo.get_tree(session)
        assert [d.depth for d in tree] == [0, 1, 1, 2]
        assert tree[0].id == root.id
        # children are accessible without raising DetachedInstanceError after expire
        session.expire_all()
        again = directory_repo.get_tree(session)
        root_row = next(d for d in again if d.id == root.id)
        assert {c.name for c in root_row.children} == {"a", "b"}


class TestGetById:
    def test_returns_directory(self, session):
        d = directory_repo.get_or_create(session, _spec("/lib", "lib"))
        assert directory_repo.get_by_id(session, d.id).id == d.id

    def test_returns_none_when_missing(self, session):
        assert directory_repo.get_by_id(session, directory_id=999) is None


class TestGetStatusCounts:
    """Per-directory file counts grouped by FileStatus."""

    def test_groups_by_status_per_directory(self, session):
        d1 = directory_repo.get_or_create(session, _spec("/a", "a"))
        d2 = directory_repo.get_or_create(session, _spec("/b", "b"))

        file_repo.get_or_create(session, d1.id, "p1.epub", FileAttrs(extension="epub"))
        file_repo.get_or_create(session, d1.id, "p2.epub", FileAttrs(extension="epub"))
        f_enr = file_repo.get_or_create(session, d1.id, "e.epub", FileAttrs(extension="epub"))
        f_acc = file_repo.get_or_create(session, d2.id, "a.epub", FileAttrs(extension="epub"))

        # Drive through the state machine to land on enriched / accepted.
        file_repo.update_status(session, f_enr.id, FileStatus.reading)
        file_repo.update_status(session, f_enr.id, FileStatus.enriched)
        file_repo.update_status(session, f_acc.id, FileStatus.reading)
        file_repo.update_status(session, f_acc.id, FileStatus.enriched)
        file_repo.update_status(session, f_acc.id, FileStatus.accepted)

        counts = directory_repo.get_status_counts(session)
        assert counts[d1.id] == DirectoryStats(
            file_count=3, pending_count=2, enriched_count=1, accepted_count=0,
        )
        assert counts[d2.id] == DirectoryStats(
            file_count=1, pending_count=0, enriched_count=0, accepted_count=1,
        )

    def test_returns_empty_dict_when_no_files(self, session):
        directory_repo.get_or_create(session, _spec("/empty", "empty"))
        assert directory_repo.get_status_counts(session) == {}

    def test_failed_and_rejected_files_count_toward_total_only(self, session):
        d = directory_repo.get_or_create(session, _spec("/a", "a"))
        f = file_repo.get_or_create(session, d.id, "x.epub", FileAttrs(extension="epub"))
        file_repo.update_status(session, f.id, FileStatus.failed)

        counts = directory_repo.get_status_counts(session)
        assert counts[d.id] == DirectoryStats(
            file_count=1, pending_count=0, enriched_count=0, accepted_count=0,
        )


class TestGetStatsForDirectory:
    def test_returns_counts_for_one_directory(self, session):
        d = directory_repo.get_or_create(session, _spec("/a", "a"))
        file_repo.get_or_create(session, d.id, "p.epub", FileAttrs(extension="epub"))
        f_enr = file_repo.get_or_create(session, d.id, "e.epub", FileAttrs(extension="epub"))
        file_repo.update_status(session, f_enr.id, FileStatus.reading)
        file_repo.update_status(session, f_enr.id, FileStatus.enriched)

        stats = directory_repo.get_stats_for_directory(session, d.id)
        assert stats == DirectoryStats(
            file_count=2, pending_count=1, enriched_count=1, accepted_count=0,
        )

    def test_returns_zeroed_when_no_files(self, session):
        d = directory_repo.get_or_create(session, _spec("/empty", "empty"))
        assert directory_repo.get_stats_for_directory(session, d.id) == DirectoryStats(0, 0, 0, 0)


class TestStatsFor:
    def test_returns_stored_stats_when_present(self):
        stats = DirectoryStats(file_count=4, pending_count=1, enriched_count=2, accepted_count=1)
        assert directory_repo.stats_for({7: stats}, directory_id=7) is stats

    def test_returns_zeroed_stats_when_missing(self):
        result = directory_repo.stats_for({}, directory_id=7)
        assert result == DirectoryStats(0, 0, 0, 0)
