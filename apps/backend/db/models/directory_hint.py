"""DirectoryHint: AI-generated summary per directory; history kept via is_current flag."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.directory import Directory


class DirectoryHint(Base):
    __tablename__ = "directory_hints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    directory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("directories.id", ondelete="CASCADE"), nullable=False
    )
    is_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    data: Mapped[Any] = mapped_column(JSON, nullable=False)
    schema_version: Mapped[str] = mapped_column(
        String(16), nullable=False, default="1", server_default="1"
    )
    ai_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    directory: Mapped["Directory"] = relationship("Directory", back_populates="hints")
