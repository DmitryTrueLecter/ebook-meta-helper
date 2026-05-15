"""Directory model for hierarchical folder structure."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.file_record import FileRecord


class Directory(Base):
    """Directory in the filesystem hierarchy."""

    __tablename__ = "directories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(4096), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("directories.id", ondelete="CASCADE"), nullable=True
    )
    hints: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    parent: Mapped[Optional["Directory"]] = relationship(
        "Directory", remote_side=[id], back_populates="children"
    )
    children: Mapped[list["Directory"]] = relationship(
        "Directory", back_populates="parent", cascade="all, delete-orphan"
    )
    files: Mapped[list["FileRecord"]] = relationship(
        "FileRecord", back_populates="directory", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Directory id={self.id} path={self.path!r}>"
