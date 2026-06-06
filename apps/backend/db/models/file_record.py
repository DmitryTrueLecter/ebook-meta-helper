"""FileRecord: tracked ebook file with status state machine."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    CHAR,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.directory import Directory
    from db.models.metadata import Metadata
    from db.models.processing_log import ProcessingLog


class FileStatus(str, enum.Enum):
    pending = "pending"
    reading = "reading"
    read = "read"
    ai_queued = "ai_queued"
    analyze_queued = "analyze_queued"
    enriching = "enriching"
    enriched = "enriched"
    accepted = "accepted"
    rejected = "rejected"
    failed = "failed"
    missing = "missing"


class FileRecord(Base):
    __tablename__ = "file_records"
    __table_args__ = (
        UniqueConstraint("directory_id", "filename", name="uq_file_records_dir_filename"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    directory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("directories.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True)
    size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    hash: Mapped[Optional[str]] = mapped_column(CHAR(64), nullable=True)
    file_modified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[FileStatus] = mapped_column(
        Enum(FileStatus, name="file_status"),
        nullable=False,
        default=FileStatus.pending,
        server_default=FileStatus.pending.value,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    directory: Mapped["Directory"] = relationship("Directory", back_populates="files")
    metadata_records: Mapped[List["Metadata"]] = relationship(
        "Metadata", back_populates="file", cascade="all, delete-orphan"
    )
    processing_logs: Mapped[List["ProcessingLog"]] = relationship(
        "ProcessingLog", back_populates="file", cascade="all, delete-orphan"
    )
