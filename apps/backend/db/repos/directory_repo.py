"""Repository for the directories table."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from db.models.directory import Directory, DirectoryStatus
from db.models.file_record import FileRecord, FileStatus
from db.repos._query_utils import subtree_clause


@dataclass(frozen=True)
class DirectoryInput:
    """Identity tuple for `get_or_create`. `path` is unique; the rest is set on insert."""

    path: str
    name: str
    parent_id: Optional[int]
    depth: int


@dataclass(frozen=True)
class DirectoryStats:
    """Per-directory file counts grouped by the statuses surfaced in the UI."""

    file_count: int
    pending_count: int
    enriched_count: int
    accepted_count: int
    missing_count: int


_EMPTY_STATS = DirectoryStats(0, 0, 0, 0, 0)


def get_or_create(session: Session, spec: DirectoryInput) -> Directory:
    existing = session.execute(
        select(Directory).where(Directory.path == spec.path)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    directory = Directory(
        path=spec.path,
        name=spec.name,
        parent_id=spec.parent_id,
        depth=spec.depth,
    )
    session.add(directory)
    session.flush()
    return directory


def update_file_count(session: Session, directory_id: int, delta: int) -> None:
    directory = session.get(Directory, directory_id)
    if directory is None:
        raise LookupError(f"Directory {directory_id} not found")
    directory.file_count = (directory.file_count or 0) + delta
    session.flush()


def set_last_scanned(session: Session, directory_id: int) -> None:
    directory = session.get(Directory, directory_id)
    if directory is None:
        raise LookupError(f"Directory {directory_id} not found")
    directory.last_scanned_at = datetime.now()
    session.flush()


def get_tree(session: Session) -> list[Directory]:
    """Active directories with `children` eagerly loaded; archived (`missing`) excluded."""
    stmt = (
        select(Directory)
        .options(selectinload(Directory.children))
        .where(Directory.status == DirectoryStatus.active)
    )
    return _ordered_tree(session, stmt)


def get_tree_including_missing(session: Session) -> list[Directory]:
    """Every directory with `children` eagerly loaded, including archived (`missing`) ones."""
    stmt = select(Directory).options(selectinload(Directory.children))
    return _ordered_tree(session, stmt)


def _ordered_tree(session: Session, stmt: Select[tuple[Directory]]) -> list[Directory]:
    stmt = stmt.order_by(Directory.depth.asc(), Directory.path.asc())
    return list(session.execute(stmt).scalars())


def get_by_id(session: Session, directory_id: int) -> Optional[Directory]:
    return session.get(Directory, directory_id)


def get_status_counts(session: Session) -> dict[int, DirectoryStats]:
    """Aggregate file counts per directory in a single query — keyed by directory_id."""
    rows = session.execute(
        select(
            FileRecord.directory_id,
            FileRecord.status,
            func.count(FileRecord.id),
        ).group_by(FileRecord.directory_id, FileRecord.status)
    ).all()

    pending: dict[int, int] = {}
    enriched: dict[int, int] = {}
    accepted: dict[int, int] = {}
    missing: dict[int, int] = {}
    totals: dict[int, int] = {}
    for directory_id, status, count in rows:
        totals[directory_id] = totals.get(directory_id, 0) + count
        if status == FileStatus.pending:
            pending[directory_id] = count
        elif status == FileStatus.enriched:
            enriched[directory_id] = count
        elif status == FileStatus.accepted:
            accepted[directory_id] = count
        elif status == FileStatus.missing:
            missing[directory_id] = count

    return {
        directory_id: DirectoryStats(
            file_count=totals[directory_id],
            pending_count=pending.get(directory_id, 0),
            enriched_count=enriched.get(directory_id, 0),
            accepted_count=accepted.get(directory_id, 0),
            missing_count=missing.get(directory_id, 0),
        )
        for directory_id in totals
    }


def stats_for(stats: dict[int, DirectoryStats], directory_id: int) -> DirectoryStats:
    """Lookup helper — returns zeroed stats when a directory has no files yet."""
    return stats.get(directory_id, _EMPTY_STATS)


def get_stats_for_directory(session: Session, directory_id: int) -> DirectoryStats:
    """Scoped variant of `get_status_counts` for a single directory."""
    rows = session.execute(
        select(FileRecord.status, func.count(FileRecord.id))
        .where(FileRecord.directory_id == directory_id)
        .group_by(FileRecord.status)
    ).all()

    by_status = {status_value: count for status_value, count in rows}
    return DirectoryStats(
        file_count=sum(by_status.values()),
        pending_count=by_status.get(FileStatus.pending, 0),
        enriched_count=by_status.get(FileStatus.enriched, 0),
        accepted_count=by_status.get(FileStatus.accepted, 0),
        missing_count=by_status.get(FileStatus.missing, 0),
    )


_HISTORY_BEARING_STATUSES = (FileStatus.accepted, FileStatus.rejected)


@dataclass(frozen=True)
class DirectoryReconcileResult:
    """Per-call tally for logging — counts of each reconcile outcome."""

    deleted: int
    archived: int
    recovered: int
    live_child_anomalies: tuple[str, ...]


def _norm_path(path: str) -> str:
    """Canonicalize a path for comparison: collapse '//', '/./', and any trailing '/'.

    Lexical only — does NOT resolve symlinks, so it is filesystem-independent and safe to
    run anywhere (prod, tests). This makes the FS↔DB reconcile robust to textual format
    drift between the scanner's output and historically-stored Directory.path values —
    the mismatch that previously caused an entire on-disk tree to be retired at once.
    """
    return os.path.normpath(path)


def _is_descendant_path(candidate: str, ancestor: str) -> bool:
    return candidate.startswith(ancestor + "/")


def reconcile_missing_directories(
    session: Session, root_path: str, present_dir_paths: set[str]
) -> DirectoryReconcileResult:
    """Bottom-up: hard-delete history-free gone dirs, archive history-bearing ones, recover reappeared ones."""
    directories = list(
        session.execute(
            select(Directory).where(subtree_clause(root_path))
        ).scalars()
    )
    history_paths = _directory_paths_with_history(session, root_path)
    present_norm = {_norm_path(p) for p in present_dir_paths}

    recovered = _recover_reappeared(directories, present_norm)

    # SAFETY GUARD against catastrophic mass-retire.
    # A healthy scan of an existing tree always re-finds the directories still on disk.
    # If the scan reported paths but NONE of the DB directories under root match any of
    # them, the two sides are out of textual sync (legacy path format, or a partial/failed
    # scan) — NOT a real "everything was deleted from disk". Retiring here would wipe the
    # whole subtree (the production incident). Refuse: recovery already ran (non-destructive),
    # retire is skipped and the mismatch is surfaced as an anomaly for the operator.
    if directories and present_norm and all(
        _norm_path(d.path) not in present_norm for d in directories
    ):
        return DirectoryReconcileResult(
            deleted=0,
            archived=0,
            recovered=recovered,
            live_child_anomalies=(f"retire-skipped:path-mismatch:{root_path}",),
        )

    deleted, archived, anomalies = _retire_gone_directories(
        session, directories, present_norm, history_paths
    )
    session.flush()
    return DirectoryReconcileResult(
        deleted=deleted,
        archived=archived,
        recovered=recovered,
        live_child_anomalies=tuple(anomalies),
    )


def _directory_paths_with_history(session: Session, root_path: str) -> set[str]:
    """Paths of directories under root that own at least one accepted/rejected file."""
    rows = session.execute(
        select(Directory.path)
        .join(FileRecord, FileRecord.directory_id == Directory.id)
        .where(
            subtree_clause(root_path),
            FileRecord.status.in_(_HISTORY_BEARING_STATUSES),
        )
        .distinct()
    ).scalars()
    return set(rows)


def _recover_reappeared(
    directories: list[Directory], present_dir_paths: set[str]
) -> int:
    recovered = 0
    for directory in directories:
        if _norm_path(directory.path) in present_dir_paths and directory.status == DirectoryStatus.missing:
            directory.status = DirectoryStatus.active
            recovered += 1
    return recovered


def _retire_gone_directories(
    session: Session,
    directories: list[Directory],
    present_dir_paths: set[str],
    history_paths: set[str],
) -> tuple[int, int, list[str]]:
    deleted = 0
    archived = 0
    anomalies: list[str] = []
    handled: set[int] = set()
    # Deepest-first so a gone child is retired before its gone parent's subtree is processed.
    for directory in sorted(directories, key=lambda d: d.depth, reverse=True):
        if directory.id in handled or _norm_path(directory.path) in present_dir_paths:
            continue
        if _has_live_descendant(directory.path, directories, present_dir_paths):
            anomalies.append(directory.path)
            continue
        if _subtree_has_history(directory.path, history_paths):
            archived += _archive_subtree(directory, directories, handled)
        else:
            deleted += _delete_subtree(session, directory, directories, handled)
    return deleted, archived, anomalies


def _has_live_descendant(
    path: str, directories: list[Directory], present_dir_paths: set[str]
) -> bool:
    return any(
        _is_descendant_path(other.path, path) and _norm_path(other.path) in present_dir_paths
        for other in directories
    )


def _subtree_has_history(path: str, history_paths: set[str]) -> bool:
    return any(
        hist == path or _is_descendant_path(hist, path) for hist in history_paths
    )


def _subtree_members(root: Directory, directories: list[Directory]) -> list[Directory]:
    return [
        directory
        for directory in directories
        if directory.path == root.path or _is_descendant_path(directory.path, root.path)
    ]


def _archive_subtree(
    root: Directory, directories: list[Directory], handled: set[int]
) -> int:
    archived = 0
    for directory in _subtree_members(root, directories):
        if directory.id in handled:
            continue
        handled.add(directory.id)
        if directory.status != DirectoryStatus.missing:
            directory.status = DirectoryStatus.missing
            archived += 1
    return archived


def _delete_subtree(
    session: Session,
    root: Directory,
    directories: list[Directory],
    handled: set[int],
) -> int:
    members = [d for d in _subtree_members(root, directories) if d.id not in handled]
    # Deepest-first ORM delete — a single well-defined path, not raw FK cascade.
    for directory in sorted(members, key=lambda d: d.depth, reverse=True):
        handled.add(directory.id)
        session.delete(directory)
    return len(members)
