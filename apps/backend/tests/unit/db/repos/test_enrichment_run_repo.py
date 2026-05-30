"""Unit tests for db.repos.enrichment_run_repo — create / finish / fail lifecycle."""

from __future__ import annotations

from decimal import Decimal

import pytest

from db.models.directory import Directory
from db.models.enrichment_run import EnrichmentStatus, EnrichmentTrigger
from db.repos import enrichment_run_repo
from db.repos.enrichment_run_repo import EnrichmentRunInput, EnrichmentRunResult


def _new_directory(session) -> Directory:
    d = Directory(path="/lib", name="lib", depth=0)
    session.add(d)
    session.flush()
    return d


def _open(directory_id, trigger=EnrichmentTrigger.scan, **extra) -> EnrichmentRunInput:
    return EnrichmentRunInput(directory_id=directory_id, trigger=trigger, **extra)


class TestCreate:
    def test_starts_in_running(self, session):
        d = _new_directory(session)
        run = enrichment_run_repo.create(
            session,
            EnrichmentRunInput(
                directory_id=d.id,
                trigger=EnrichmentTrigger.scan,
                ai_model="gpt-4o-mini",
                prompt_version="v1",
            ),
        )
        assert run.id is not None
        assert run.status == EnrichmentStatus.running
        assert run.trigger == EnrichmentTrigger.scan
        assert run.ai_model == "gpt-4o-mini"
        assert run.started_at is not None
        assert run.finished_at is None

    def test_directory_id_optional(self, session):
        run = enrichment_run_repo.create(
            session, _open(None, trigger=EnrichmentTrigger.user_file)
        )
        assert run.directory_id is None
        assert run.trigger == EnrichmentTrigger.user_file


class TestFinish:
    def test_closes_run_with_counters(self, session):
        run = enrichment_run_repo.create(session, _open(None))
        closed = enrichment_run_repo.finish(
            session,
            run.id,
            EnrichmentRunResult(
                success_count=4, failure_count=1, cost_usd=Decimal("0.0123")
            ),
        )
        assert closed.status == EnrichmentStatus.done
        assert closed.success_count == 4
        assert closed.failure_count == 1
        assert closed.cost_usd == Decimal("0.0123")
        assert closed.finished_at is not None

    def test_finish_twice_rejected(self, session):
        run = enrichment_run_repo.create(session, _open(None))
        enrichment_run_repo.finish(
            session, run.id, EnrichmentRunResult(success_count=1, failure_count=0)
        )
        with pytest.raises(ValueError):
            enrichment_run_repo.finish(
                session, run.id, EnrichmentRunResult(success_count=1, failure_count=0)
            )

    def test_raises_on_missing(self, session):
        with pytest.raises(LookupError):
            enrichment_run_repo.finish(
                session,
                run_id=999,
                outcome=EnrichmentRunResult(success_count=0, failure_count=0),
            )


class TestFindLatestRunning:
    def test_returns_none_when_no_runs(self, session):
        result = enrichment_run_repo.find_latest_running(
            session, directory_id=None, trigger=EnrichmentTrigger.user_file
        )
        assert result is None

    def test_returns_latest_running_for_directory_and_trigger(self, session):
        d = _new_directory(session)
        enrichment_run_repo.create(session, _open(d.id, trigger=EnrichmentTrigger.user_file))
        run_two = enrichment_run_repo.create(
            session, _open(d.id, trigger=EnrichmentTrigger.user_file)
        )
        result = enrichment_run_repo.find_latest_running(
            session, directory_id=d.id, trigger=EnrichmentTrigger.user_file
        )
        assert result is not None
        assert result.id == run_two.id

    def test_ignores_closed_runs(self, session):
        d = _new_directory(session)
        run = enrichment_run_repo.create(session, _open(d.id, trigger=EnrichmentTrigger.user_file))
        enrichment_run_repo.finish(
            session, run.id, EnrichmentRunResult(success_count=1, failure_count=0)
        )
        result = enrichment_run_repo.find_latest_running(
            session, directory_id=d.id, trigger=EnrichmentTrigger.user_file
        )
        assert result is None

    def test_filters_by_trigger(self, session):
        d = _new_directory(session)
        enrichment_run_repo.create(session, _open(d.id, trigger=EnrichmentTrigger.scan))
        result = enrichment_run_repo.find_latest_running(
            session, directory_id=d.id, trigger=EnrichmentTrigger.user_file
        )
        assert result is None


class TestFail:
    def test_marks_failed_with_message(self, session):
        run = enrichment_run_repo.create(session, _open(None))
        failed = enrichment_run_repo.fail(session, run.id, error_message="OpenAI 500")
        assert failed.status == EnrichmentStatus.failed
        assert failed.error_message == "OpenAI 500"
        assert failed.finished_at is not None

    def test_fail_after_done_rejected(self, session):
        run = enrichment_run_repo.create(session, _open(None))
        enrichment_run_repo.finish(
            session, run.id, EnrichmentRunResult(success_count=0, failure_count=0)
        )
        with pytest.raises(ValueError):
            enrichment_run_repo.fail(session, run.id, "late")
