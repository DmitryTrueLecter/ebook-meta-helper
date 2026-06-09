"""Unit tests for db.repos.ai_call_repo (SQLite — chain persistence + canonical assignment)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.ai.outcome import AICallRecord, EnrichOutcome
from app.models.book import BookRecord
from db.models.ai_call import AICallOrigin
from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentRun, EnrichmentTrigger
from db.models.file_record import FileRecord
from db.repos import ai_call_repo
from db.repos.ai_call_repo import AICallInput


def _new_file(session) -> FileRecord:
    d = Directory(path="/lib", name="lib", depth=0)
    session.add(d)
    session.flush()
    f = FileRecord(directory_id=d.id, filename="book.epub")
    session.add(f)
    session.flush()
    return f


def _new_run(session) -> EnrichmentRun:
    run = EnrichmentRun(trigger=EnrichmentTrigger.scan)
    session.add(run)
    session.flush()
    return run


def _book() -> BookRecord:
    return BookRecord(
        path="/lib/book.epub",
        original_filename="book.epub",
        extension="epub",
        directories=["lib"],
    )


def _call(sequence: int, tier: str, confidence: str) -> AICallRecord:
    return AICallRecord(
        sequence=sequence,
        tier=tier,
        model="gpt-4o-mini",
        response_format_ref="book_metadata.v2",
        system_prompt="sys",
        user_prompt="user",
        raw_response="{}",
        duration_ms=120,
        confidence=Decimal(confidence),
    )


class TestRecordCalls:
    def test_persists_whole_chain_with_one_canonical(self, session):
        f = _new_file(session)
        outcome = EnrichOutcome(
            record=_book(),
            calls=[_call(0, "cheap", "0.500"), _call(1, "expensive", "0.900")],
            canonical_sequence=1,
        )
        records = ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=None,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            outcome,
        )
        session.commit()

        canonical = [r for r in records if r.is_canonical]
        assert len(canonical) == 1
        assert canonical[0].sequence == 1
        assert {r.sequence for r in records} == {0, 1}

    def test_canonical_can_be_the_cheap_call(self, session):
        f = _new_file(session)
        outcome = EnrichOutcome(
            record=_book(),
            calls=[_call(0, "cheap", "0.950"), _call(1, "expensive", "0.400")],
            canonical_sequence=0,
        )
        records = ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=None,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            outcome,
        )
        canonical = [r for r in records if r.is_canonical]
        assert len(canonical) == 1
        assert canonical[0].sequence == 0

    def test_empty_chain_is_rejected(self, session):
        f = _new_file(session)
        with pytest.raises(ValueError):
            ai_call_repo.record_calls(
                session,
                AICallInput(
                    file_id=f.id,
                    enrichment_run_id=None,
                    config_version_id=None,
                    origin=AICallOrigin.pipeline,
                ),
                EnrichOutcome(record=_book(), calls=[], canonical_sequence=0),
            )

    def test_canonical_sequence_not_in_chain_is_rejected(self, session):
        f = _new_file(session)
        with pytest.raises(ValueError):
            ai_call_repo.record_calls(
                session,
                AICallInput(
                    file_id=f.id,
                    enrichment_run_id=None,
                    config_version_id=None,
                    origin=AICallOrigin.sandbox,
                ),
                EnrichOutcome(
                    record=_book(),
                    calls=[_call(0, "cheap", "0.500")],
                    canonical_sequence=5,
                ),
            )


class TestGetChain:
    def test_returns_chain_ordered_by_sequence(self, session):
        f = _new_file(session)
        ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=None,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            EnrichOutcome(
                record=_book(),
                calls=[_call(1, "expensive", "0.9"), _call(0, "cheap", "0.5")],
                canonical_sequence=1,
            ),
        )
        session.commit()

        chain = ai_call_repo.get_chain(session, f.id, None)
        assert [c.sequence for c in chain] == [0, 1]

    def test_sandbox_chain_isolated_from_run_chain(self, session):
        f = _new_file(session)
        ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=None,
                config_version_id=None,
                origin=AICallOrigin.sandbox,
            ),
            EnrichOutcome(
                record=_book(),
                calls=[_call(0, "cheap", "0.5")],
                canonical_sequence=0,
            ),
        )
        session.commit()

        sandbox_chain = ai_call_repo.get_chain(session, f.id, None)
        assert len(sandbox_chain) == 1
        assert sandbox_chain[0].origin == AICallOrigin.sandbox


class TestGetForFile:
    def test_returns_all_calls_for_file(self, session):
        f = _new_file(session)
        ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=None,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            EnrichOutcome(
                record=_book(),
                calls=[_call(0, "cheap", "0.5"), _call(1, "expensive", "0.9")],
                canonical_sequence=1,
            ),
        )
        session.commit()
        assert len(ai_call_repo.get_for_file(session, f.id)) == 2


class TestGetForRun:
    def test_returns_all_calls_for_run(self, session):
        f = _new_file(session)
        run = _new_run(session)
        ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=run.id,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            EnrichOutcome(
                record=_book(),
                calls=[_call(0, "cheap", "0.5"), _call(1, "expensive", "0.9")],
                canonical_sequence=1,
            ),
        )
        session.commit()

        calls = ai_call_repo.get_for_run(session, run.id)
        assert len(calls) == 2
        assert {c.sequence for c in calls} == {0, 1}
        assert all(c.enrichment_run_id == run.id for c in calls)

    def test_excludes_calls_from_other_run(self, session):
        f = _new_file(session)
        target_run = _new_run(session)
        other_run = _new_run(session)
        ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=target_run.id,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            EnrichOutcome(
                record=_book(),
                calls=[_call(0, "cheap", "0.5")],
                canonical_sequence=0,
            ),
        )
        ai_call_repo.record_calls(
            session,
            AICallInput(
                file_id=f.id,
                enrichment_run_id=other_run.id,
                config_version_id=None,
                origin=AICallOrigin.pipeline,
            ),
            EnrichOutcome(
                record=_book(),
                calls=[_call(0, "cheap", "0.7"), _call(1, "expensive", "0.95")],
                canonical_sequence=1,
            ),
        )
        session.commit()

        calls = ai_call_repo.get_for_run(session, target_run.id)
        assert len(calls) == 1
        assert all(c.enrichment_run_id == target_run.id for c in calls)
