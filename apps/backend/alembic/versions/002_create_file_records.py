"""Create file_records table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("directory_id", sa.BigInteger(), nullable=False),
        sa.Column("sort_order", sa.Numeric(10, 4), nullable=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("format", sa.String(50), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("file_modified_at", sa.DateTime(), nullable=False),
        sa.Column(
            "discovered_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["directory_id"], ["directories.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_file_records_directory_id", "file_records", ["directory_id"])
    op.create_index("ix_file_records_hash", "file_records", ["hash"])
    op.create_unique_constraint(
        "uq_file_records_dir_filename", "file_records", ["directory_id", "filename"]
    )


def downgrade() -> None:
    op.drop_table("file_records")
