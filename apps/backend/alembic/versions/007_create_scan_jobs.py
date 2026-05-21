"""Create scan_jobs table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SCAN_JOB_STATUS_VALUES = ("pending", "running", "done", "failed", "cancelled")


def upgrade() -> None:
    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("root_directory_id", sa.Integer(), nullable=True),
        sa.Column("root_path", sa.String(length=1024), nullable=False),
        sa.Column(
            "status",
            mysql.ENUM(*SCAN_JOB_STATUS_VALUES, name="scan_job_status"),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "files_discovered",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "files_processed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("current_file_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["root_directory_id"], ["directories.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["current_file_id"], ["file_records.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_scan_jobs_status_created",
        "scan_jobs",
        ["status", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_scan_jobs_status_created", table_name="scan_jobs")
    op.drop_table("scan_jobs")
