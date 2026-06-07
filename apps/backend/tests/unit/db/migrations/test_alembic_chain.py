"""Render alembic 001-007 in offline mode and assert it matches the ORM schema."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from db.base import Base
import db.models  # noqa: F401 — register all models with Base.metadata


BACKEND_DIR = Path(__file__).resolve().parents[4]
EXPECTED_TABLES = {
    "directories",
    "directory_hints",
    "file_records",
    "enrichment_runs",
    "metadata",
    "processing_logs",
    "scan_jobs",
}
EXPECTED_REVISIONS = ("001", "002", "003", "004", "005", "006", "007", "008", "009")


def _run_alembic(*args: str) -> str:
    env = os.environ.copy()
    env["DATABASE_URL"] = "mysql+pymysql://u:p@h/d"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


@pytest.fixture(scope="module")
def upgrade_sql() -> str:
    return _run_alembic("upgrade", "head", "--sql")


@pytest.fixture(scope="module")
def downgrade_sql() -> str:
    return _run_alembic("downgrade", "head:base", "--sql")


class TestRevisionChain:
    def test_all_revisions_applied_in_order(self, upgrade_sql):
        running = re.findall(r"Running upgrade (\S*) -> (\d+)", upgrade_sql)
        applied = [to_rev for _, to_rev in running]
        assert applied == list(EXPECTED_REVISIONS)

    def test_every_orm_table_is_created(self, upgrade_sql):
        created = set(re.findall(r"CREATE TABLE (\w+)", upgrade_sql))
        missing = EXPECTED_TABLES - created
        assert not missing, f"missing CREATE TABLE for: {missing}"

    def test_orm_metadata_tables_match_expected(self):
        orm_tables = {t.name for t in Base.metadata.sorted_tables}
        assert EXPECTED_TABLES <= orm_tables

    def test_downgrade_drops_every_table(self, downgrade_sql):
        dropped = set(re.findall(r"DROP TABLE (\w+)", downgrade_sql))
        assert EXPECTED_TABLES <= dropped


class TestDirectoriesDDL:
    def test_unique_path_constraint(self, upgrade_sql):
        assert re.search(r"UNIQUE \(path\)", upgrade_sql)

    def test_self_fk_set_null(self, upgrade_sql):
        assert re.search(
            r"FOREIGN KEY\(parent_id\) REFERENCES directories \(id\) ON DELETE SET NULL",
            upgrade_sql,
        )

    def test_parent_id_indexes(self, upgrade_sql):
        assert "CREATE INDEX ix_directories_parent_id ON directories (parent_id)" in upgrade_sql
        assert (
            "CREATE INDEX ix_directories_parent_id_name ON directories (parent_id, name)"
            in upgrade_sql
        )


class TestDirectoryHintsDDL:
    def test_fk_cascade(self, upgrade_sql):
        assert re.search(
            r"FOREIGN KEY\(directory_id\) REFERENCES directories \(id\) ON DELETE CASCADE",
            upgrade_sql,
        )

    def test_json_data_column(self, upgrade_sql):
        assert re.search(r"data JSON NOT NULL", upgrade_sql)

    def test_indexes(self, upgrade_sql):
        assert (
            "CREATE INDEX ix_directory_hints_dir_current ON directory_hints "
            "(directory_id, is_current)" in upgrade_sql
        )
        assert (
            "CREATE INDEX ix_directory_hints_dir_created ON directory_hints "
            "(directory_id, created_at DESC)" in upgrade_sql
        )


class TestFileRecordsDDL:
    def test_status_enum_values(self, upgrade_sql):
        match = re.search(r"status ENUM\(([^)]+)\)", upgrade_sql)
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {
            "pending",
            "reading",
            "ai_queued",
            "enriching",
            "enriched",
            "accepted",
            "rejected",
            "failed",
        }

    def test_unique_dir_filename(self, upgrade_sql):
        assert "UNIQUE (directory_id, filename)" in upgrade_sql

    def test_updated_at_on_update_clause(self, upgrade_sql):
        assert (
            "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP "
            "ON UPDATE CURRENT_TIMESTAMP" in upgrade_sql
        )

    def test_hash_is_char64(self, upgrade_sql):
        assert "hash CHAR(64)" in upgrade_sql

    def test_required_indexes(self, upgrade_sql):
        assert "CREATE INDEX ix_file_records_status ON file_records (status)" in upgrade_sql
        assert (
            "CREATE INDEX ix_file_records_dir_status ON file_records (directory_id, status)"
            in upgrade_sql
        )
        assert (
            "CREATE INDEX ix_file_records_dir_sort_filename ON file_records "
            "(directory_id, sort_order, filename)" in upgrade_sql
        )
        assert "CREATE INDEX ix_file_records_hash ON file_records (hash)" in upgrade_sql
        assert (
            "CREATE INDEX ix_file_records_updated_at ON file_records (updated_at DESC)"
            in upgrade_sql
        )


class TestEnrichmentRunsDDL:
    def test_trigger_enum_values(self, upgrade_sql):
        match = re.search(r"`trigger` ENUM\(([^)]+)\)", upgrade_sql)
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {"scan", "user_directory", "user_file", "retry"}

    def test_enrichment_status_enum_values(self, upgrade_sql):
        # all ENUM(...) tokens between the start of CREATE TABLE enrichment_runs
        # and the next CREATE TABLE
        block = _table_block(upgrade_sql, "enrichment_runs")
        statuses = re.findall(r"status ENUM\(([^)]+)\)", block)
        values = {v.strip().strip("'") for v in statuses[0].split(",")}
        assert values == {"running", "done", "failed", "cancelled"}

    def test_both_fks_set_null(self, upgrade_sql):
        assert (
            "FOREIGN KEY(directory_id) REFERENCES directories (id) ON DELETE SET NULL"
            in upgrade_sql
        )
        assert (
            "FOREIGN KEY(directory_hint_id) REFERENCES directory_hints (id) "
            "ON DELETE SET NULL" in upgrade_sql
        )

    def test_counters_default_zero(self, upgrade_sql):
        block = _table_block(upgrade_sql, "enrichment_runs")
        assert "file_count INTEGER NOT NULL DEFAULT 0" in block
        assert "success_count INTEGER NOT NULL DEFAULT 0" in block
        assert "failure_count INTEGER NOT NULL DEFAULT 0" in block


class TestMetadataDDL:
    def test_source_enum_values(self, upgrade_sql):
        block = _table_block(upgrade_sql, "metadata")
        match = re.search(r"source ENUM\(([^)]+)\)", block)
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {"file", "ai", "accepted", "manual"}

    def test_data_required_json(self, upgrade_sql):
        block = _table_block(upgrade_sql, "metadata")
        assert "data JSON NOT NULL" in block

    def test_isbn_columns_created_char_then_widened(self, upgrade_sql):
        # 005 creates the columns as CHAR; 009 widens them to VARCHAR(20) so
        # separator-bearing real-world ISBNs fit (DMI-139).
        block = _table_block(upgrade_sql, "metadata")
        assert "isbn13 CHAR(13)" in block
        assert "isbn10 CHAR(10)" in block
        assert "ALTER TABLE metadata MODIFY isbn13 VARCHAR(20)" in upgrade_sql
        assert "ALTER TABLE metadata MODIFY isbn10 VARCHAR(20)" in upgrade_sql

    def test_fks(self, upgrade_sql):
        assert (
            "FOREIGN KEY(file_id) REFERENCES file_records (id) ON DELETE CASCADE"
            in upgrade_sql
        )
        assert (
            "FOREIGN KEY(enrichment_run_id) REFERENCES enrichment_runs (id) "
            "ON DELETE SET NULL" in upgrade_sql
        )

    def test_required_indexes(self, upgrade_sql):
        assert (
            "CREATE INDEX ix_metadata_file_source_current ON metadata "
            "(file_id, source, is_current)" in upgrade_sql
        )
        assert (
            "CREATE INDEX ix_metadata_file_source_created ON metadata "
            "(file_id, source, created_at DESC)" in upgrade_sql
        )
        assert "CREATE INDEX ix_metadata_confidence ON metadata (confidence)" in upgrade_sql
        assert (
            "CREATE INDEX ix_metadata_series_index ON metadata (series, series_index)"
            in upgrade_sql
        )
        assert "CREATE INDEX ix_metadata_language ON metadata (language)" in upgrade_sql


class TestProcessingLogsDDL:
    def test_step_enum_values(self, upgrade_sql):
        block = _table_block(upgrade_sql, "processing_logs")
        match = re.search(r"step ENUM\(([^)]+)\)", block)
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {
            "scan_discover",
            "scan_rehash",
            "read_metadata",
            "summarize_dir",
            "ai_enrich",
            "write_back",
            "move_or_rename",
        }

    def test_level_enum_values(self, upgrade_sql):
        block = _table_block(upgrade_sql, "processing_logs")
        match = re.search(r"level ENUM\(([^)]+)\)", block)
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {"info", "warn", "error"}

    def test_datetime_fsp3(self, upgrade_sql):
        block = _table_block(upgrade_sql, "processing_logs")
        assert "created_at DATETIME(3) NOT NULL DEFAULT CURRENT_TIMESTAMP(3)" in block

    def test_message_widened_to_text(self, upgrade_sql):
        # 006 creates message as VARCHAR(1024); 009 widens it to TEXT so the wrapped
        # DataError + SQL text from a failed insert fits without a second crash (DMI-139).
        block = _table_block(upgrade_sql, "processing_logs")
        assert "message VARCHAR(1024)" in block
        assert "ALTER TABLE processing_logs MODIFY message TEXT" in upgrade_sql

    def test_indexes(self, upgrade_sql):
        assert (
            "CREATE INDEX ix_processing_logs_file_created ON processing_logs "
            "(file_id, created_at DESC)" in upgrade_sql
        )
        assert (
            "CREATE INDEX ix_processing_logs_enrichment_run ON processing_logs "
            "(enrichment_run_id)" in upgrade_sql
        )


class TestScanJobsDDL:
    def test_status_enum_values(self, upgrade_sql):
        block = _table_block(upgrade_sql, "scan_jobs")
        match = re.search(r"status ENUM\(([^)]+)\)", block)
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {"pending", "running", "done", "failed", "cancelled"}

    def test_fks_set_null(self, upgrade_sql):
        assert (
            "FOREIGN KEY(root_directory_id) REFERENCES directories (id) ON DELETE SET NULL"
            in upgrade_sql
        )
        assert (
            "FOREIGN KEY(current_file_id) REFERENCES file_records (id) ON DELETE SET NULL"
            in upgrade_sql
        )

    def test_status_created_index(self, upgrade_sql):
        assert (
            "CREATE INDEX ix_scan_jobs_status_created ON scan_jobs "
            "(status, created_at DESC)" in upgrade_sql
        )


class TestLifecycleStatesMigration:
    """008 alters the file_status/enrichment_trigger ENUMs, adds directories.status,
    and remaps stuck/legacy rows — verified against the offline-rendered SQL."""

    def test_directory_status_column_added(self, upgrade_sql):
        assert re.search(
            r"ALTER TABLE directories ADD COLUMN status "
            r"ENUM\('active',\s*'missing'\)",
            upgrade_sql,
        )

    def test_file_status_enum_gains_new_values(self, upgrade_sql):
        match = re.search(
            r"ALTER TABLE file_records MODIFY status ENUM\(([^)]+)\)", upgrade_sql
        )
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert {"read", "analyze_queued", "missing"} <= values
        assert {
            "pending",
            "reading",
            "read",
            "ai_queued",
            "analyze_queued",
            "enriching",
            "enriched",
            "accepted",
            "rejected",
            "failed",
            "missing",
        } == values

    def test_enrichment_trigger_enum_drops_user_directory(self, upgrade_sql):
        match = re.search(
            r"ALTER TABLE enrichment_runs MODIFY `trigger` ENUM\(([^)]+)\)",
            upgrade_sql,
        )
        assert match
        values = {v.strip().strip("'") for v in match.group(1).split(",")}
        assert values == {"scan", "user_file", "retry"}
        assert "user_directory" not in values

    def test_stuck_ai_queued_rows_remapped(self, upgrade_sql):
        assert (
            "UPDATE file_records SET status = 'analyze_queued' "
            "WHERE status = 'ai_queued'" in upgrade_sql
        )

    def test_legacy_user_directory_rows_remapped(self, upgrade_sql):
        assert (
            "UPDATE enrichment_runs SET `trigger` = 'user_file' "
            "WHERE `trigger` = 'user_directory'" in upgrade_sql
        )

    def test_downgrade_restores_old_enums_and_drops_status(self, downgrade_sql):
        assert "ALTER TABLE directories DROP COLUMN status" in downgrade_sql
        file_status = re.search(
            r"ALTER TABLE file_records MODIFY status ENUM\(([^)]+)\)", downgrade_sql
        )
        assert file_status
        restored = {v.strip().strip("'") for v in file_status.group(1).split(",")}
        assert "analyze_queued" not in restored
        assert "missing" not in restored


def _table_block(sql: str, table: str) -> str:
    """Return the substring covering one CREATE TABLE statement for `table`."""
    pattern = rf"CREATE TABLE {table} \((.*?)\);"
    match = re.search(pattern, sql, re.DOTALL)
    assert match, f"CREATE TABLE {table} not found"
    return match.group(1)
