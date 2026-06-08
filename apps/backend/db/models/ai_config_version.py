"""AIConfigVersion: AI runtime configuration as versioned data; single active row at a time."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AIConfigVersion(Base):
    __tablename__ = "ai_config_versions"
    __table_args__ = (
        UniqueConstraint("version", name="uq_ai_config_versions_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    cheap_model: Mapped[str] = mapped_column(String(64), nullable=False)
    expensive_model: Mapped[str] = mapped_column(String(64), nullable=False)
    effort: Mapped[str] = mapped_column(String(16), nullable=False)
    escalation_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, default="openai", server_default="openai"
    )
    response_format_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
