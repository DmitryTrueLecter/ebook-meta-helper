"""AI calls API: per-file call list and single-call detail (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import AICallDetail, AICallSummary
from db.models.ai_call import AICall
from db.repos import ai_call_repo

router = APIRouter(prefix="/api", tags=["ai-calls"])


@router.get("/files/{file_id}/ai-calls", response_model=list[AICallSummary])
def list_file_ai_calls(file_id: int, db: Session = Depends(get_db)) -> list[AICallSummary]:
    """Every AI call logged for the file — newest first; list view without prompt/response text."""
    calls = ai_call_repo.get_for_file(db, file_id)
    return [_to_summary(call) for call in calls]


@router.get("/ai-calls/{call_id}", response_model=AICallDetail)
def get_ai_call_detail(call_id: int, db: Session = Depends(get_db)) -> AICallDetail:
    """Full AI call including prompts, raw response, and provenance."""
    call = ai_call_repo.get_by_id(db, call_id)
    if call is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI call {call_id} not found",
        )
    return _to_detail(call)


def _to_summary(call: AICall) -> AICallSummary:
    return AICallSummary(
        id=call.id,
        file_id=call.file_id,
        enrichment_run_id=call.enrichment_run_id,
        sequence=call.sequence,
        tier=call.tier.value,
        is_canonical=call.is_canonical,
        model=call.model,
        confidence=float(call.confidence) if call.confidence is not None else None,
        prompt_tokens=call.prompt_tokens,
        completion_tokens=call.completion_tokens,
        cost_usd=float(call.cost_usd) if call.cost_usd is not None else None,
        duration_ms=call.duration_ms,
        created_at=call.created_at,
    )


def _to_detail(call: AICall) -> AICallDetail:
    return AICallDetail(
        id=call.id,
        file_id=call.file_id,
        enrichment_run_id=call.enrichment_run_id,
        sequence=call.sequence,
        tier=call.tier.value,
        is_canonical=call.is_canonical,
        model=call.model,
        confidence=float(call.confidence) if call.confidence is not None else None,
        prompt_tokens=call.prompt_tokens,
        completion_tokens=call.completion_tokens,
        cost_usd=float(call.cost_usd) if call.cost_usd is not None else None,
        duration_ms=call.duration_ms,
        created_at=call.created_at,
        system_prompt=call.system_prompt,
        user_prompt=call.user_prompt,
        raw_response=call.raw_response,
        response_format_ref=call.response_format_ref,
        effort=call.effort,
        parse_errors=call.parse_errors,
        origin=call.origin.value,
        config_version_id=call.config_version_id,
    )
