"""ProcessingLog: per-step pipeline log entries replacing on-disk JSON debug files."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.enrichment_run import EnrichmentRun
    from db.models.file_record import FileRecord


class ProcessingStep(str, enum.Enum):
    scan_discover = "scan_discover"
    scan_rehash = "scan_rehash"
    read_metadata = "read_metadata"
    summarize_dir = "summarize_dir"
    ai_enrich = "ai_enrich"
    write_back = "write_back"
    move_or_rename = "move_or_rename"


class ProcessingLogLevel(str, enum.Enum):
    info = "info"
    warn = "warn"
    error = "error"


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False
    )
    enrichment_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("enrichment_runs.id", ondelete="SET NULL"), nullable=True
    )
    step: Mapped[ProcessingStep] = mapped_column(
        Enum(ProcessingStep, name="processing_step"), nullable=False
    )
    level: Mapped[ProcessingLogLevel] = mapped_column(
        Enum(ProcessingLogLevel, name="processing_log_level"),
        nullable=False,
        default=ProcessingLogLevel.info,
        server_default=ProcessingLogLevel.info.value,
    )
    message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False).with_variant(mysql.DATETIME(fsp=3), "mysql", "mariadb"),
        nullable=False,
        server_default=func.now(3),
    )

    file: Mapped["FileRecord"] = relationship("FileRecord", back_populates="processing_logs")
    enrichment_run: Mapped[Optional["EnrichmentRun"]] = relationship("EnrichmentRun")
