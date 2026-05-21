"""Create file_records table.

Revision ID: 003
Revises: 002
Create Date: 2026-05-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FILE_STATUS_VALUES = (
    "pending",
    "reading",
    "ai_queued",
    "enriching",
    "enriched",
    "accepted",
    "rejected",
    "failed",
)


def upgrade() -> None:
    op.create_table(
        "file_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("directory_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("extension", sa.String(length=16), nullable=True),
        sa.Column("format", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Numeric(10, 4), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("hash", sa.CHAR(length=64), nullable=True),
        sa.Column("file_modified_at", sa.DateTime(), nullable=True),
        sa.Column(
            "status",
            mysql.ENUM(*FILE_STATUS_VALUES, name="file_status"),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["directory_id"], ["directories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "directory_id", "filename", name="uq_file_records_dir_filename"
        ),
    )
    op.create_index("ix_file_records_status", "file_records", ["status"])
    op.create_index(
        "ix_file_records_dir_status", "file_records", ["directory_id", "status"]
    )
    op.create_index(
        "ix_file_records_dir_sort_filename",
        "file_records",
        ["directory_id", "sort_order", "filename"],
    )
    op.create_index("ix_file_records_hash", "file_records", ["hash"])
    op.create_index(
        "ix_file_records_updated_at",
        "file_records",
        [sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_file_records_updated_at", table_name="file_records")
    op.drop_index("ix_file_records_hash", table_name="file_records")
    op.drop_index("ix_file_records_dir_sort_filename", table_name="file_records")
    op.drop_index("ix_file_records_dir_status", table_name="file_records")
    op.drop_index("ix_file_records_status", table_name="file_records")
    op.drop_table("file_records")
