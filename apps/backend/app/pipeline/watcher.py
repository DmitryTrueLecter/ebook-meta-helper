"""DB-driven watcher loop: poll NEW_BOOKS_DIR, drive one scan cycle per interval."""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv

from app.pipeline.scan_cycle import CycleResult, run_scan_cycle
from db.session import get_session
from db.repos import file_repo


def run_watcher() -> None:
    load_dotenv()

    new_books_dir = _require_env("NEW_BOOKS_DIR")
    sleep_seconds = int(os.environ.get("WATCH_SLEEP_SECONDS", "10"))

    print(f"[watcher] watching NEW_BOOKS_DIR: {new_books_dir}")
    print(f"[watcher] sleep when idle: {sleep_seconds}s")

    reset_count = _reset_stalled_on_startup()
    if reset_count:
        print(f"[watcher] recovery: reset {reset_count} stalled file records to pending")

    while True:
        try:
            result = run_scan_cycle(new_books_dir)
            _report_cycle(result)
        except Exception as exc:
            print(f"[watcher] scan cycle failed: {exc}")
        time.sleep(sleep_seconds)


def _reset_stalled_on_startup() -> int:
    """Run the in-flight → pending reset in a single short session."""
    with get_session() as session:
        return file_repo.reset_stalled_to_pending(session)


def _report_cycle(result: CycleResult) -> None:
    if result.files_discovered == 0:
        return
    print(
        f"[watcher] scan_job={result.scan_job_id} "
        f"discovered={result.files_discovered} "
        f"processed={result.files_processed} "
        f"failed={result.files_failed}"
    )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set")
    return value
