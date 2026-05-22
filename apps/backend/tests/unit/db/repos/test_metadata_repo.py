"""Unit tests for db.repos.metadata_repo — (file_id, source) is_current invariant."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from db.models.directory import Directory
from db.models.file_record import FileRecord
from db.models.metadata import Metadata, MetadataSource
from db.repos import metadata_repo
from db.repos.metadata_repo import MetadataInput, MetadataScalars


def _new_file(session, filename: str = "book.epub") -> FileRecord:
    d = (
        session.query(Directory).filter(Directory.path == "/lib").first()
        or Directory(path="/lib", name="lib", depth=0)
    )
    if d.id is None:
        session.add(d)
        session.flush()
    f = FileRecord(directory_id=d.id, filename=filename)
    session.add(f)
    session.flush()
    return f


def _input(file_id: int, source: MetadataSource, **extra) -> MetadataInput:
    return MetadataInput(
        file_id=file_id,
        source=source,
        data=extra.pop("data", {"k": "v"}),
        **extra,
    )


class TestCreate:
    def test_inserts_with_scalars_and_data(self, session):
        f = _new_file(session)
        m = metadata_repo.create(
            session,
            MetadataInput(
                file_id=f.id,
                source=MetadataSource.ai,
                data={"authors": ["Frank Herbert"], "tags": ["scifi"]},
                scalars=MetadataScalars(
                    title="Dune",
                    language="en",
                    series="Dune",
                    series_index=1,
                    isbn13="9780441013593",
                    confidence=Decimal("0.950"),
                ),
            ),
        )
        assert m.id is not None
        assert m.is_current is True
        assert m.title == "Dune"
        assert m.series == "Dune"
        assert m.series_index == 1
        assert m.data["authors"] == ["Frank Herbert"]
        assert m.confidence == Decimal("0.950")

    def test_flips_previous_same_source(self, session):
        f = _new_file(session)
        first = metadata_repo.create(session, _input(f.id, MetadataSource.ai))
        second = metadata_repo.create(session, _input(f.id, MetadataSource.ai))

        session.refresh(first)
        session.refresh(second)
        assert first.is_current is False
        assert second.is_current is True

    def test_different_sources_coexist_as_current(self, session):
        f = _new_file(session)
        m_file = metadata_repo.create(session, _input(f.id, MetadataSource.file))
        m_ai = metadata_repo.create(session, _input(f.id, MetadataSource.ai))
        m_accepted = metadata_repo.create(
            session, _input(f.id, MetadataSource.accepted)
        )

        for m in (m_file, m_ai, m_accepted):
            session.refresh(m)
            assert m.is_current is True

    def test_at_most_one_current_per_file_source(self, session):
        f = _new_file(session)
        for i in range(3):
            metadata_repo.create(
                session, _input(f.id, MetadataSource.ai, data={"v": i})
            )

        current_rows = session.execute(
            select(Metadata).where(
                Metadata.file_id == f.id,
                Metadata.source == MetadataSource.ai,
                Metadata.is_current.is_(True),
            )
        ).scalars().all()
        assert len(current_rows) == 1
        assert current_rows[0].data["v"] == 2

    def test_other_files_untouched(self, session):
        f1 = _new_file(session, "a.epub")
        f2 = _new_file(session, "b.epub")
        m1 = metadata_repo.create(session, _input(f1.id, MetadataSource.ai))
        m2 = metadata_repo.create(session, _input(f2.id, MetadataSource.ai))
        # new AI snapshot for f1 must not affect f2
        metadata_repo.create(session, _input(f1.id, MetadataSource.ai))

        session.refresh(m1)
        session.refresh(m2)
        assert m1.is_current is False
        assert m2.is_current is True


class TestGetCurrent:
    def test_returns_latest_for_source(self, session):
        f = _new_file(session)
        metadata_repo.create(session, _input(f.id, MetadataSource.ai, data={"v": 1}))
        latest = metadata_repo.create(
            session, _input(f.id, MetadataSource.ai, data={"v": 2})
        )

        result = metadata_repo.get_current(session, f.id, MetadataSource.ai)
        assert result is not None
        assert result.id == latest.id

    def test_returns_none_when_source_missing(self, session):
        f = _new_file(session)
        metadata_repo.create(session, _input(f.id, MetadataSource.file))
        assert metadata_repo.get_current(session, f.id, MetadataSource.ai) is None


class TestGetHistory:
    def test_returns_all_versions_newest_first(self, session):
        f = _new_file(session)
        metadata_repo.create(session, _input(f.id, MetadataSource.file, data={"v": 1}))
        metadata_repo.create(session, _input(f.id, MetadataSource.ai, data={"v": 2}))
        metadata_repo.create(session, _input(f.id, MetadataSource.ai, data={"v": 3}))

        history = metadata_repo.get_history(session, f.id)
        assert len(history) == 3
        # newest first by id (created_at is server_default — may collide on fast SQLite)
        assert history[0].data["v"] == 3
        assert history[-1].data["v"] == 1

    def test_returns_empty_for_unknown_file(self, session):
        assert metadata_repo.get_history(session, file_id=999) == []


class TestFindFilesWithAiSuggestion:
    def test_returns_subset_with_current_ai_metadata(self, session):
        f1 = _new_file(session, "a.epub")
        f2 = _new_file(session, "b.epub")
        f3 = _new_file(session, "c.epub")

        metadata_repo.create(session, _input(f1.id, MetadataSource.ai, data={"v": 1}))
        metadata_repo.create(session, _input(f2.id, MetadataSource.file, data={"v": 2}))
        # f3: no metadata at all

        result = metadata_repo.find_files_with_ai_suggestion(
            session, [f1.id, f2.id, f3.id]
        )
        assert result == {f1.id}

    def test_superseded_ai_row_does_not_appear(self, session):
        f = _new_file(session, "a.epub")
        first = metadata_repo.create(session, _input(f.id, MetadataSource.ai, data={"v": 1}))
        metadata_repo.create(session, _input(f.id, MetadataSource.ai, data={"v": 2}))

        session.refresh(first)
        assert first.is_current is False  # flipped by the second insert

        result = metadata_repo.find_files_with_ai_suggestion(session, [f.id])
        assert result == {f.id}  # the still-current second row keeps it in the set

    def test_empty_input_returns_empty_set(self, session):
        assert metadata_repo.find_files_with_ai_suggestion(session, []) == set()
