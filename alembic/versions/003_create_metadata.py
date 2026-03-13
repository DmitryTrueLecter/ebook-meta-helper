"""Create metadata table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metadata",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("data", mysql.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["file_id"], ["file_records.id"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_metadata_file_id", "metadata", ["file_id"])
    op.create_index("ix_metadata_source", "metadata", ["source"])


def downgrade() -> None:
    op.drop_table("metadata")
