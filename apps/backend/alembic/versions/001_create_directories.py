"""Create directories table.

Revision ID: 001
Revises:
Create Date: 2026-03-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "directories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("path", sa.String(4096), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.BigInteger(), nullable=True),
        sa.Column("hints", mysql.JSON(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["directories.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("path"),
    )
    op.create_index("ix_directories_parent_id", "directories", ["parent_id"])


def downgrade() -> None:
    op.drop_table("directories")
