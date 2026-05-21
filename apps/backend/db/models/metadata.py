"""Metadata: hybrid scalar+JSON snapshot of file metadata; history kept via is_current flag."""

from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.enrichment_run import EnrichmentRun
    from db.models.file_record import FileRecord


class MetadataSource(str, enum.Enum):
    file = "file"
    ai = "ai"
    accepted = "accepted"
    manual = "manual"


class Metadata(Base):
    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[MetadataSource] = mapped_column(
        Enum(MetadataSource, name="metadata_source"), nullable=False
    )
    enrichment_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("enrichment_runs.id", ondelete="SET NULL"), nullable=True
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    subtitle: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    series: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    series_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    series_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    isbn13: Mapped[Optional[str]] = mapped_column(String(13), nullable=True)
    isbn10: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    asin: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    published: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    year: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    data: Mapped[Any] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1", server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    file: Mapped["FileRecord"] = relationship("FileRecord", back_populates="metadata_records")
    enrichment_run: Mapped[Optional["EnrichmentRun"]] = relationship("EnrichmentRun")
