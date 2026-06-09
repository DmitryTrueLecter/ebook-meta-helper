"""Repository for ai_calls — persists a whole escalation chain with exactly one canonical row."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.outcome import EnrichOutcome
from db.models.ai_call import AICall, AICallOrigin


@dataclass(frozen=True)
class AICallInput:
    """Persistence context for a chain — identity and provenance the provider does not own."""

    file_id: int
    enrichment_run_id: Optional[int]
    config_version_id: Optional[int]
    origin: AICallOrigin


def record_calls(
    session: Session, context: AICallInput, outcome: EnrichOutcome
) -> list[AICall]:
    """Insert every call in the chain; exactly one row gets is_canonical=True per outcome.canonical_sequence."""
    if not outcome.calls:
        raise ValueError("EnrichOutcome carries no calls to record")

    canonical = outcome.canonical_sequence
    if not any(call.sequence == canonical for call in outcome.calls):
        raise ValueError(
            f"canonical_sequence {canonical} matches no call in the chain"
        )

    records = [
        AICall(
            file_id=context.file_id,
            enrichment_run_id=context.enrichment_run_id,
            config_version_id=context.config_version_id,
            origin=context.origin,
            sequence=call.sequence,
            tier=call.tier,
            is_canonical=call.sequence == canonical,
            model=call.model,
            effort=call.effort,
            response_format_ref=call.response_format_ref,
            system_prompt=call.system_prompt,
            user_prompt=call.user_prompt,
            raw_response=call.raw_response,
            prompt_tokens=call.prompt_tokens,
            completion_tokens=call.completion_tokens,
            cost_usd=call.cost_usd,
            duration_ms=call.duration_ms,
            confidence=call.confidence,
            parse_errors=call.parse_errors,
        )
        for call in outcome.calls
    ]
    session.add_all(records)
    session.flush()
    return records


def get_by_id(session: Session, call_id: int) -> Optional[AICall]:
    return session.get(AICall, call_id)


def get_for_file(session: Session, file_id: int) -> list[AICall]:
    return list(
        session.execute(
            select(AICall)
            .where(AICall.file_id == file_id)
            .order_by(AICall.created_at.desc(), AICall.id.desc())
        ).scalars()
    )


def get_for_run(session: Session, enrichment_run_id: int) -> list[AICall]:
    return list(
        session.execute(
            select(AICall)
            .where(AICall.enrichment_run_id == enrichment_run_id)
            .order_by(AICall.created_at.desc(), AICall.id.desc())
        ).scalars()
    )


def get_chain(
    session: Session, file_id: int, enrichment_run_id: Optional[int]
) -> list[AICall]:
    """Return one file/run escalation chain ordered by call sequence."""
    run_predicate = (
        AICall.enrichment_run_id.is_(None)
        if enrichment_run_id is None
        else AICall.enrichment_run_id == enrichment_run_id
    )
    return list(
        session.execute(
            select(AICall)
            .where(AICall.file_id == file_id, run_predicate)
            .order_by(AICall.sequence.asc(), AICall.id.asc())
        ).scalars()
    )
