"""Create processing_logs table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROCESSING_STEP_VALUES = (
    "scan_discover",
    "scan_rehash",
    "read_metadata",
    "summarize_dir",
    "ai_enrich",
    "write_back",
    "move_or_rename",
)
PROCESSING_LOG_LEVEL_VALUES = ("info", "warn", "error")


def upgrade() -> None:
    op.create_table(
        "processing_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("enrichment_run_id", sa.Integer(), nullable=True),
        sa.Column(
            "step",
            mysql.ENUM(*PROCESSING_STEP_VALUES, name="processing_step"),
            nullable=False,
        ),
        sa.Column(
            "level",
            mysql.ENUM(*PROCESSING_LOG_LEVEL_VALUES, name="processing_log_level"),
            nullable=False,
            server_default=sa.text("'info'"),
        ),
        sa.Column("message", sa.String(length=1024), nullable=True),
        sa.Column("details", mysql.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=3),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP(3)"),
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
        "ix_processing_logs_file_created",
        "processing_logs",
        ["file_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_processing_logs_enrichment_run",
        "processing_logs",
        ["enrichment_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_logs_enrichment_run", table_name="processing_logs")
    op.drop_index("ix_processing_logs_file_created", table_name="processing_logs")
    op.drop_table("processing_logs")
