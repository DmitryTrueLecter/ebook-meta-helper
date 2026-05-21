"""Create enrichment_runs table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENRICHMENT_TRIGGER_VALUES = ("scan", "user_directory", "user_file", "retry")
ENRICHMENT_STATUS_VALUES = ("running", "done", "failed", "cancelled")


def upgrade() -> None:
    op.create_table(
        "enrichment_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("directory_id", sa.Integer(), nullable=True),
        sa.Column("directory_hint_id", sa.Integer(), nullable=True),
        sa.Column(
            "trigger",
            mysql.ENUM(*ENRICHMENT_TRIGGER_VALUES, name="enrichment_trigger"),
            nullable=False,
        ),
        sa.Column(
            "status",
            mysql.ENUM(*ENRICHMENT_STATUS_VALUES, name="enrichment_status"),
            nullable=False,
            server_default=sa.text("'running'"),
        ),
        sa.Column("ai_model", sa.String(length=64), nullable=True),
        sa.Column("prompt_version", sa.String(length=32), nullable=True),
        sa.Column(
            "file_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "success_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "failure_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["directory_id"], ["directories.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["directory_hint_id"], ["directory_hints.id"], ondelete="SET NULL"
        ),
    )


def downgrade() -> None:
    op.drop_table("enrichment_runs")
