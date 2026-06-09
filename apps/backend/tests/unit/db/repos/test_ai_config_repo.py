"""Unit tests for db.repos.ai_config_repo (SQLite — version assignment + activate flip)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from db.repos import ai_config_repo
from db.repos.ai_config_repo import AIConfigVersionInput


def _input(label: str = "v") -> AIConfigVersionInput:
    return AIConfigVersionInput(
        system_prompt="prompt",
        cheap_model="gpt-4o-mini",
        expensive_model="gpt-4o-mini",
        effort="high",
        escalation_threshold=Decimal("0.700"),
        response_format_ref="book_metadata.v2",
        label=label,
    )


class TestCreateVersion:
    def test_first_version_is_one_and_inactive(self, session):
        record = ai_config_repo.create_version(session, _input())
        session.commit()
        assert record.version == 1
        assert record.is_active is False
        assert record.provider == "openai"

    def test_versions_are_monotonic(self, session):
        a = ai_config_repo.create_version(session, _input("a"))
        b = ai_config_repo.create_version(session, _input("b"))
        c = ai_config_repo.create_version(session, _input("c"))
        session.commit()
        assert [a.version, b.version, c.version] == [1, 2, 3]


class TestActivate:
    def test_activate_sets_target_active(self, session):
        record = ai_config_repo.create_version(session, _input())
        ai_config_repo.activate(session, record.id)
        session.commit()
        assert ai_config_repo.get_active(session).id == record.id

    def test_activate_flips_previous_off(self, session):
        first = ai_config_repo.create_version(session, _input("a"))
        second = ai_config_repo.create_version(session, _input("b"))
        ai_config_repo.activate(session, first.id)
        ai_config_repo.activate(session, second.id)
        session.commit()

        session.refresh(first)
        assert first.is_active is False
        assert ai_config_repo.get_active(session).id == second.id

    def test_activate_unknown_id_raises(self, session):
        with pytest.raises(LookupError):
            ai_config_repo.activate(session, 999)


class TestGetActive:
    def test_returns_none_when_no_active_version(self, session):
        ai_config_repo.create_version(session, _input())
        session.commit()
        assert ai_config_repo.get_active(session) is None


class TestListVersions:
    def test_newest_version_first(self, session):
        ai_config_repo.create_version(session, _input("a"))
        ai_config_repo.create_version(session, _input("b"))
        session.commit()
        assert [v.version for v in ai_config_repo.list_versions(session)] == [2, 1]
