"""Repository for metadata — enforces at most one is_current=True per (file_id, source)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.models.metadata import Metadata, MetadataSource


@dataclass(frozen=True)
class MetadataScalars:
    """Indexed scalar fields stored alongside the JSON data blob — all optional."""

    title: Optional[str] = None
    subtitle: Optional[str] = None
    language: Optional[str] = None
    series: Optional[str] = None
    series_index: Optional[int] = None
    series_total: Optional[int] = None
    publisher: Optional[str] = None
    isbn13: Optional[str] = None
    isbn10: Optional[str] = None
    asin: Optional[str] = None
    published: Optional[date] = None
    year: Optional[int] = None
    confidence: Optional[Decimal] = None


@dataclass(frozen=True)
class MetadataInput:
    """Full payload for a metadata snapshot — identity, JSON body, optional scalars."""

    file_id: int
    source: MetadataSource
    data: dict[str, Any]
    enrichment_run_id: Optional[int] = None
    scalars: MetadataScalars = field(default_factory=MetadataScalars)


def create(session: Session, payload: MetadataInput) -> Metadata:
    """Insert a new is_current=True row and flip the prior current row for (file_id, source) to False."""
    session.execute(
        update(Metadata)
        .where(
            Metadata.file_id == payload.file_id,
            Metadata.source == payload.source,
            Metadata.is_current.is_(True),
        )
        .values(is_current=False)
    )

    record = Metadata(
        file_id=payload.file_id,
        source=payload.source,
        enrichment_run_id=payload.enrichment_run_id,
        is_current=True,
        data=payload.data,
        **{f.name: getattr(payload.scalars, f.name) for f in fields(payload.scalars)},
    )
    session.add(record)
    session.flush()
    return record


def get_current(
    session: Session, file_id: int, source: MetadataSource
) -> Optional[Metadata]:
    return session.execute(
        select(Metadata).where(
            Metadata.file_id == file_id,
            Metadata.source == source,
            Metadata.is_current.is_(True),
        )
    ).scalar_one_or_none()


def get_history(session: Session, file_id: int) -> list[Metadata]:
    return list(
        session.execute(
            select(Metadata)
            .where(Metadata.file_id == file_id)
            .order_by(Metadata.created_at.desc(), Metadata.id.desc())
        ).scalars()
    )
