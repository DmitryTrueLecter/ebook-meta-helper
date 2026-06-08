"""EnrichmentRun: one batch of AI enrichment calls grouped by directory or trigger."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.directory import Directory
    from db.models.directory_hint import DirectoryHint


class EnrichmentTrigger(str, enum.Enum):
    scan = "scan"
    user_file = "user_file"
    retry = "retry"


class EnrichmentStatus(str, enum.Enum):
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class EnrichmentRun(Base):
    __tablename__ = "enrichment_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    directory_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("directories.id", ondelete="SET NULL"), nullable=True
    )
    directory_hint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("directory_hints.id", ondelete="SET NULL"), nullable=True
    )
    trigger: Mapped[EnrichmentTrigger] = mapped_column(
        Enum(EnrichmentTrigger, name="enrichment_trigger"), nullable=False
    )
    status: Mapped[EnrichmentStatus] = mapped_column(
        Enum(EnrichmentStatus, name="enrichment_status"),
        nullable=False,
        default=EnrichmentStatus.running,
        server_default=EnrichmentStatus.running.value,
    )
    ai_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    success_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    directory: Mapped[Optional["Directory"]] = relationship("Directory")
    directory_hint: Mapped[Optional["DirectoryHint"]] = relationship("DirectoryHint")
