"""Create directory_hints table.

Revision ID: 002
Revises: 001
Create Date: 2026-05-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "directory_hints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("directory_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("data", mysql.JSON(), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'1'"),
        ),
        sa.Column("ai_model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["directory_id"], ["directories.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_directory_hints_dir_current",
        "directory_hints",
        ["directory_id", "is_current"],
    )
    op.create_index(
        "ix_directory_hints_dir_created",
        "directory_hints",
        ["directory_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_directory_hints_dir_created", table_name="directory_hints")
    op.drop_index("ix_directory_hints_dir_current", table_name="directory_hints")
    op.drop_table("directory_hints")
