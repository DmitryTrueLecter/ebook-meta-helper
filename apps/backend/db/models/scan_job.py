"""ScanJob: live scan progress for the UI progress bar."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.directory import Directory
    from db.models.file_record import FileRecord


class ScanJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_directory_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("directories.id", ondelete="SET NULL"), nullable=True
    )
    root_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    status: Mapped[ScanJobStatus] = mapped_column(
        Enum(ScanJobStatus, name="scan_job_status"),
        nullable=False,
        default=ScanJobStatus.pending,
        server_default=ScanJobStatus.pending.value,
    )
    files_discovered: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    files_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    current_file_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("file_records.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    root_directory: Mapped[Optional["Directory"]] = relationship("Directory")
    current_file: Mapped[Optional["FileRecord"]] = relationship("FileRecord")
