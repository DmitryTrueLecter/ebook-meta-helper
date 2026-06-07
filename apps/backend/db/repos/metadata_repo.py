"""Repository for metadata — enforces at most one is_current=True per (file_id, source)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from datetime import date
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.models.metadata import Metadata, MetadataSource

# ISBN-bearing scalars: real-world values arrive with separators (0-306-40615-2) that
# overflow the fixed-width CHAR columns. Strip to digits + X check char before storing.
_ISBN_FIELDS = frozenset({"isbn10", "isbn13"})


def _fit_scalar(column_name: str, value: Any) -> Any:
    """Normalize + truncate a scalar to its column so arbitrary ebook metadata can never
    overflow and raise mid-discover (the prod incident: a dashed ISBN exceeding CHAR(10),
    which crashed the whole scan cycle)."""
    if not isinstance(value, str):
        return value
    if column_name in _ISBN_FIELDS:
        value = re.sub(r"[^0-9Xx]", "", value).upper()
    limit = getattr(Metadata.__table__.c[column_name].type, "length", None)
    if limit is not None and len(value) > limit:
        value = value[:limit]
    return value


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
        **{
            f.name: _fit_scalar(f.name, getattr(payload.scalars, f.name))
            for f in fields(payload.scalars)
        },
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


def find_files_with_ai_suggestion(
    session: Session, file_ids: list[int]
) -> set[int]:
    """Return the subset of file_ids that have a current AI metadata snapshot."""
    if not file_ids:
        return set()
    rows = session.execute(
        select(Metadata.file_id)
        .where(
            Metadata.file_id.in_(file_ids),
            Metadata.source == MetadataSource.ai,
            Metadata.is_current.is_(True),
        )
        .distinct()
    ).scalars()
    return set(rows)
