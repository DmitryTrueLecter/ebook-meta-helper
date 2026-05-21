"""Create metadata table.

Revision ID: 005
Revises: 004
Create Date: 2026-05-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


METADATA_SOURCE_VALUES = ("file", "ai", "accepted", "manual")


def upgrade() -> None:
    op.create_table(
        "metadata",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            mysql.ENUM(*METADATA_SOURCE_VALUES, name="metadata_source"),
            nullable=False,
        ),
        sa.Column("enrichment_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "is_current",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("subtitle", sa.String(length=512), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("series", sa.String(length=255), nullable=True),
        sa.Column("series_index", sa.Integer(), nullable=True),
        sa.Column("series_total", sa.Integer(), nullable=True),
        sa.Column("publisher", sa.String(length=255), nullable=True),
        sa.Column("isbn13", sa.CHAR(length=13), nullable=True),
        sa.Column("isbn10", sa.CHAR(length=10), nullable=True),
        sa.Column("asin", sa.String(length=16), nullable=True),
        sa.Column("published", sa.Date(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("data", mysql.JSON(), nullable=False),
        sa.Column(
            "schema_version",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'1'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["file_id"], ["file_records.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["enrichment_run_id"], ["enrichment_runs.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_metadata_file_source_current",
        "metadata",
        ["file_id", "source", "is_current"],
    )
    op.create_index(
        "ix_metadata_file_source_created",
        "metadata",
        ["file_id", "source", sa.text("created_at DESC")],
    )
    op.create_index("ix_metadata_confidence", "metadata", ["confidence"])
    op.create_index(
        "ix_metadata_series_index", "metadata", ["series", "series_index"]
    )
    op.create_index("ix_metadata_language", "metadata", ["language"])


def downgrade() -> None:
    op.drop_index("ix_metadata_language", table_name="metadata")
    op.drop_index("ix_metadata_series_index", table_name="metadata")
    op.drop_index("ix_metadata_confidence", table_name="metadata")
    op.drop_index("ix_metadata_file_source_created", table_name="metadata")
    op.drop_index("ix_metadata_file_source_current", table_name="metadata")
    op.drop_table("metadata")
