"""FileRecord model for tracked files."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.directory import Directory


class FileRecord(Base):
    """A file discovered in the filesystem."""

    __tablename__ = "file_records"
    __table_args__ = (
        sa.UniqueConstraint("directory_id", "filename", name="uq_file_records_dir_filename"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    directory_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("directories.id", ondelete="CASCADE"), nullable=False
    )
    sort_order: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    format: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    file_modified_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    directory: Mapped["Directory"] = relationship("Directory", back_populates="files")

    def __repr__(self) -> str:
        return f"<FileRecord id={self.id} filename={self.filename!r}>"
