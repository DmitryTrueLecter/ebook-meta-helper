"""AI config API: active version and full version list (read-only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.schemas import AIConfigVersionView
from db.models.ai_config_version import AIConfigVersion
from db.repos import ai_config_repo

router = APIRouter(prefix="/api/ai-config", tags=["ai-config"])


@router.get("/active", response_model=AIConfigVersionView)
def get_active_ai_config(db: Session = Depends(get_db)) -> AIConfigVersionView:
    """The currently active AI config version; 404 when none is active."""
    active = ai_config_repo.get_active(db)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active AI config version",
        )
    return _to_view(active)


@router.get("/versions", response_model=list[AIConfigVersionView])
def list_ai_config_versions(db: Session = Depends(get_db)) -> list[AIConfigVersionView]:
    """All AI config versions — highest version number first."""
    versions = ai_config_repo.list_versions(db)
    return [_to_view(version) for version in versions]


def _to_view(version: AIConfigVersion) -> AIConfigVersionView:
    return AIConfigVersionView(
        id=version.id,
        version=version.version,
        label=version.label,
        system_prompt=version.system_prompt,
        cheap_model=version.cheap_model,
        expensive_model=version.expensive_model,
        effort=version.effort,
        escalation_threshold=float(version.escalation_threshold),
        provider=version.provider,
        response_format_ref=version.response_format_ref,
        is_active=version.is_active,
        created_at=version.created_at,
        created_by=version.created_by,
    )
