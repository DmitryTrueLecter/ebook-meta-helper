"""Create directories table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "directories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("path", sa.String(length=768), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_scanned_at", sa.DateTime(), nullable=True),
        sa.Column(
            "discovered_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["directories.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("path", name="uq_directories_path"),
    )
    op.create_index("ix_directories_parent_id", "directories", ["parent_id"])
    op.create_index("ix_directories_parent_id_name", "directories", ["parent_id", "name"])


def downgrade() -> None:
    op.drop_index("ix_directories_parent_id_name", table_name="directories")
    op.drop_index("ix_directories_parent_id", table_name="directories")
    op.drop_table("directories")
