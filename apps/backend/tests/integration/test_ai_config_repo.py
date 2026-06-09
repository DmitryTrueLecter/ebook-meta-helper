"""AIConfigVersion single-active invariant against real MariaDB (DMI-144).

Requires a real session: the invariant is the transactional flip in activate(), which the
SQLite unit suite cannot exercise the way production MariaDB does.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.ai_config_version import AIConfigVersion
from db.repos import ai_config_repo
from db.repos.ai_config_repo import AIConfigVersionInput


def _input(label: str) -> AIConfigVersionInput:
    return AIConfigVersionInput(
        system_prompt="prompt",
        cheap_model="gpt-4o-mini",
        expensive_model="gpt-4o-mini",
        effort="high",
        escalation_threshold=Decimal("0.700"),
        response_format_ref="book_metadata.v2",
        label=label,
    )


def _active_ids(session: Session) -> list[int]:
    return list(
        session.execute(
            select(AIConfigVersion.id).where(AIConfigVersion.is_active.is_(True))
        ).scalars()
    )


class TestSingleActiveInvariant:
    def test_activate_flips_previous_active_off_same_transaction(self, session):
        first = ai_config_repo.create_version(session, _input("v1"))
        second = ai_config_repo.create_version(session, _input("v2"))
        session.commit()

        ai_config_repo.activate(session, first.id)
        session.commit()
        assert _active_ids(session) == [first.id]

        ai_config_repo.activate(session, second.id)
        # Assert before commit: the flip must hold within the same transaction.
        assert _active_ids(session) == [second.id]
        session.commit()
        assert _active_ids(session) == [second.id]

    def test_get_active_returns_the_single_active_version(self, session):
        first = ai_config_repo.create_version(session, _input("v1"))
        second = ai_config_repo.create_version(session, _input("v2"))
        ai_config_repo.activate(session, second.id)
        session.commit()

        active = ai_config_repo.get_active(session)
        assert active is not None
        assert active.id == second.id
        assert first.is_active is False

    def test_create_version_assigns_monotonic_versions(self, session):
        first = ai_config_repo.create_version(session, _input("a"))
        second = ai_config_repo.create_version(session, _input("b"))
        third = ai_config_repo.create_version(session, _input("c"))
        session.commit()

        assert [first.version, second.version, third.version] == [1, 2, 3]

    def test_list_versions_orders_newest_first(self, session):
        ai_config_repo.create_version(session, _input("a"))
        ai_config_repo.create_version(session, _input("b"))
        session.commit()

        versions = [v.version for v in ai_config_repo.list_versions(session)]
        assert versions == [2, 1]
