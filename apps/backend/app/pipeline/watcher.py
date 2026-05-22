"""Filesystem-poll watcher loop.

Deactivated pending Phase 4.3 — the new `process_file` requires a DB session,
file_id, and enrichment_run_id which the watcher does not yet assemble.
"""


def run_watcher() -> None:
    raise NotImplementedError(
        "watcher must be updated to build a DB session, FileRecord, and EnrichmentRun "
        "before calling process_file (DMI-31 Phase 4.3)."
    )
