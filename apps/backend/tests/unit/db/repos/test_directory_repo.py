"""Unit tests for db.repos.directory_repo."""

from __future__ import annotations

import pytest

from db.models.directory import Directory
from db.repos import directory_repo
from db.repos.directory_repo import DirectoryInput


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
