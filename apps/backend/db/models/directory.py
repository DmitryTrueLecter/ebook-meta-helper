"""Directory: hierarchical folder tree with denormalized depth and file counts."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base

if TYPE_CHECKING:
    from db.models.directory_hint import DirectoryHint
    from db.models.file_record import FileRecord


class Directory(Base):
    __tablename__ = "directories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(768), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("directories.id", ondelete="SET NULL"), nullable=True
    )
    depth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    parent: Mapped[Optional["Directory"]] = relationship(
        "Directory", remote_side="Directory.id", back_populates="children"
    )
    children: Mapped[List["Directory"]] = relationship(
        "Directory", back_populates="parent", cascade="all"
    )
    files: Mapped[List["FileRecord"]] = relationship(
        "FileRecord", back_populates="directory", cascade="all, delete-orphan"
    )
    hints: Mapped[List["DirectoryHint"]] = relationship(
        "DirectoryHint", back_populates="directory", cascade="all, delete-orphan"
    )
