"""Shared SQL helpers for repos — LIKE escaping and subtree path matching."""

from __future__ import annotations

from sqlalchemy.sql.elements import ColumnElement

from db.models.directory import Directory


def escape_like(value: str) -> str:
    """Escape LIKE wildcards so a literal `_` in a path can't act as a single-char match."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def subtree_clause(root_path: str) -> ColumnElement[bool]:
    """Subtree rows: path == root or path starts with root + '/' (trailing /% prevents sibling-prefix cross-match)."""
    return (Directory.path == root_path) | (
        Directory.path.like(escape_like(root_path) + "/%", escape="\\")
    )
