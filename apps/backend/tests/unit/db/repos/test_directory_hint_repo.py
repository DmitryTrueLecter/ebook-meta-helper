"""Unit tests for db.repos.directory_hint_repo — `is_current` invariant."""

from __future__ import annotations

from sqlalchemy import select

from db.models.directory import Directory
from db.models.directory_hint import DirectoryHint
from db.repos import directory_hint_repo
from db.repos.directory_hint_repo import DirectoryHintInput


def _new_directory(session, path: str = "/lib") -> Directory:
    d = Directory(path=path, name=path.rsplit("/", 1)[-1] or "root", depth=0)
    session.add(d)
    session.flush()
    return d


def _hint(directory_id: int, **extra) -> DirectoryHintInput:
    data = extra.pop("data", {"k": "v"})
    return DirectoryHintInput(directory_id=directory_id, data=data, **extra)


class TestCreate:
    def test_inserts_as_current(self, session):
        d = _new_directory(session)
        hint = directory_hint_repo.create(
            session,
            DirectoryHintInput(
                directory_id=d.id,
                data={"genre": "scifi"},
                ai_model="gpt-4o-mini",
                prompt_version="v1",
            ),
        )
        assert hint.id is not None
        assert hint.is_current is True
        assert hint.data["genre"] == "scifi"
        assert hint.ai_model == "gpt-4o-mini"

    def test_flips_previous_current(self, session):
        d = _new_directory(session)
        first = directory_hint_repo.create(session, _hint(d.id, data={"v": 1}))
        second = directory_hint_repo.create(session, _hint(d.id, data={"v": 2}))

        session.refresh(first)
        session.refresh(second)
        assert first.is_current is False
        assert second.is_current is True

    def test_at_most_one_current_per_directory(self, session):
        d = _new_directory(session)
        directory_hint_repo.create(session, _hint(d.id, data={"v": 1}))
        directory_hint_repo.create(session, _hint(d.id, data={"v": 2}))
        directory_hint_repo.create(session, _hint(d.id, data={"v": 3}))

        rows = session.execute(
            select(DirectoryHint).where(
                DirectoryHint.directory_id == d.id,
                DirectoryHint.is_current.is_(True),
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].data["v"] == 3

    def test_other_directories_untouched(self, session):
        d1 = _new_directory(session)
        d2 = _new_directory(session, path="/lib2")

        h1 = directory_hint_repo.create(session, _hint(d1.id, data={"v": "d1"}))
        h2 = directory_hint_repo.create(session, _hint(d2.id, data={"v": "d2"}))
        # creating a new hint for d1 must not flip d2's current row
        directory_hint_repo.create(session, _hint(d1.id, data={"v": "d1-next"}))

        session.refresh(h1)
        session.refresh(h2)
        assert h1.is_current is False
        assert h2.is_current is True


class TestGetCurrent:
    def test_returns_latest_current(self, session):
        d = _new_directory(session)
        directory_hint_repo.create(session, _hint(d.id, data={"v": 1}))
        latest = directory_hint_repo.create(session, _hint(d.id, data={"v": 2}))

        result = directory_hint_repo.get_current(session, d.id)
        assert result is not None
        assert result.id == latest.id

    def test_returns_none_when_no_hints(self, session):
        d = _new_directory(session)
        assert directory_hint_repo.get_current(session, d.id) is None
