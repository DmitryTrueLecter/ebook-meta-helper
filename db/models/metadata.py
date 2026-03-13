"""Metadata model for file metadata from various sources."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.file_record import FileRecord


class Metadata(Base):
    """Metadata record: original from file, AI-enriched, or written back."""

    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("file_records.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    file: Mapped["FileRecord"] = relationship("FileRecord", back_populates="metadata_records")

    def __repr__(self) -> str:
        return f"<Metadata id={self.id} file_id={self.file_id} source={self.source!r}>"
