"""Repository for ai_config_versions — at most one is_active=True row at any time."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from db.models.ai_config_version import AIConfigVersion


@dataclass(frozen=True)
class AIConfigVersionInput:
    """New-version payload — runtime knobs the provider reads via the active snapshot."""

    system_prompt: str
    cheap_model: str
    expensive_model: str
    effort: str
    escalation_threshold: Decimal
    response_format_ref: str
    provider: str = "openai"
    label: Optional[str] = None
    created_by: Optional[str] = None


def get_active(session: Session) -> Optional[AIConfigVersion]:
    return session.execute(
        select(AIConfigVersion).where(AIConfigVersion.is_active.is_(True))
    ).scalar_one_or_none()


def list_versions(session: Session) -> list[AIConfigVersion]:
    return list(
        session.execute(
            select(AIConfigVersion).order_by(AIConfigVersion.version.desc())
        ).scalars()
    )


def create_version(session: Session, payload: AIConfigVersionInput) -> AIConfigVersion:
    """Insert an inactive new version with the next monotonic version number."""
    next_version = (
        session.execute(select(func.coalesce(func.max(AIConfigVersion.version), 0))).scalar_one()
        + 1
    )
    record = AIConfigVersion(
        version=next_version,
        label=payload.label,
        system_prompt=payload.system_prompt,
        cheap_model=payload.cheap_model,
        expensive_model=payload.expensive_model,
        effort=payload.effort,
        escalation_threshold=payload.escalation_threshold,
        provider=payload.provider,
        response_format_ref=payload.response_format_ref,
        is_active=False,
        created_by=payload.created_by,
    )
    session.add(record)
    session.flush()
    return record


def activate(session: Session, version_id: int) -> AIConfigVersion:
    """Flip the previously-active row off and set version_id active in the same transaction."""
    target = session.get(AIConfigVersion, version_id)
    if target is None:
        raise LookupError(f"AIConfigVersion {version_id} not found")

    session.execute(
        update(AIConfigVersion)
        .where(AIConfigVersion.is_active.is_(True), AIConfigVersion.id != version_id)
        .values(is_active=False)
    )
    target.is_active = True
    session.flush()
    return target
