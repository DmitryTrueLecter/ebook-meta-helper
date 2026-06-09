"""AICall: one model invocation (grain = single call); an escalation chain is N rows per file/run."""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.ai_config_version import AIConfigVersion
    from db.models.enrichment_run import EnrichmentRun
    from db.models.file_record import FileRecord


class AICallOrigin(str, enum.Enum):
    pipeline = "pipeline"
    sandbox = "sandbox"


class AICallTier(str, enum.Enum):
    cheap = "cheap"
    expensive = "expensive"


_LONGTEXT = Text().with_variant(mysql.LONGTEXT(), "mysql", "mariadb")


class AICall(Base):
    __tablename__ = "ai_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False
    )
    enrichment_run_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("enrichment_runs.id", ondelete="SET NULL"), nullable=True
    )
    config_version_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("ai_config_versions.id", ondelete="SET NULL"), nullable=True
    )
    origin: Mapped[AICallOrigin] = mapped_column(
        Enum(AICallOrigin, name="ai_call_origin"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tier: Mapped[AICallTier] = mapped_column(
        Enum(AICallTier, name="ai_call_tier"), nullable=False
    )
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    effort: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    response_format_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_prompt: Mapped[str] = mapped_column(_LONGTEXT, nullable=False)
    raw_response: Mapped[str] = mapped_column(_LONGTEXT, nullable=False)
    prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 6), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(4, 3), nullable=True)
    parse_errors: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False).with_variant(mysql.DATETIME(fsp=3), "mysql", "mariadb"),
        nullable=False,
        server_default=func.now(3),
    )

    file: Mapped["FileRecord"] = relationship("FileRecord")
    enrichment_run: Mapped[Optional["EnrichmentRun"]] = relationship("EnrichmentRun")
    config_version: Mapped[Optional["AIConfigVersion"]] = relationship("AIConfigVersion")
