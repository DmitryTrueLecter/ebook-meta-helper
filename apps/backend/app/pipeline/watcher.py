"""DB-driven watcher loop: consume pending ScanJob rows, fall back to a NEW_BOOKS_DIR sweep job when idle."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

from app.pipeline.scan_cycle import CycleResult, run_scan_cycle
from db.session import get_session
from db.repos import file_repo, scan_job_repo


@dataclass(frozen=True)
class _ClaimedJob:
    """A ScanJob already transitioned to running, ready for one scan cycle."""

    job_id: int
    root_path: str


def run_watcher() -> None:
    load_dotenv()

    new_books_dir = _require_env("NEW_BOOKS_DIR")
    sleep_seconds = int(os.environ.get("WATCH_SLEEP_SECONDS", "10"))

    print(f"[watcher] idle sweep root (NEW_BOOKS_DIR): {new_books_dir}")
    print(f"[watcher] sleep when idle: {sleep_seconds}s")

    reset_count = _reset_stalled_on_startup()
    if reset_count:
        print(f"[watcher] recovery: reset {reset_count} stalled file records to pending")

    while True:
        try:
            _run_one_iteration(new_books_dir)
        except Exception as exc:
            print(f"[watcher] scan cycle failed: {exc}")
        time.sleep(sleep_seconds)


def _run_one_iteration(new_books_dir: str) -> None:
    """Claim the next job and run one scan cycle against it; idle if nothing is claimable."""
    claimed = _claim_next_job(new_books_dir)
    if claimed is None:
        return
    result = run_scan_cycle(claimed.job_id, claimed.root_path)
    _report_cycle(result)


def _claim_next_job(new_books_dir: str) -> Optional[_ClaimedJob]:
    """Claim the oldest pending job; if none, enqueue + claim a NEW_BOOKS_DIR sweep job. None when nothing is claimable."""
    # The idle sweep is folded into the job model — it runs through a ScanJob row like every
    # UI-triggered scan, so the progress UI observes periodic sweeps the same way.
    with get_session() as session:
        job = scan_job_repo.claim_next_pending(session)
        if job is None:
            scan_job_repo.create(session, root_path=new_books_dir)
            session.flush()
            job = scan_job_repo.claim_next_pending(session)
        if job is None:
            return None
        return _ClaimedJob(job_id=job.id, root_path=job.root_path)


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
