"""Pydantic response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DirectoryNode(BaseModel):
    """Directory tree node with aggregated file counts and nested children."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    path: str
    depth: int
    file_count: int
    pending_count: int
    enriched_count: int
    accepted_count: int
    children: list[DirectoryNode] = Field(default_factory=list)


class FileListItem(BaseModel):
    """One row in a file listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    extension: str | None
    format: str | None
    status: str
    has_ai_suggestion: bool
    sort_order: float | None


class DirectoryDetail(BaseModel):
    """Single directory with the contained file list."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    path: str
    depth: int
    file_count: int
    pending_count: int
    enriched_count: int
    accepted_count: int
    files: list[FileListItem] = Field(default_factory=list)


class PaginatedFiles(BaseModel):
    """Paginated file listing — `items` plus page metadata."""

    items: list[FileListItem]
    total: int
    page: int
    page_size: int


class MetadataSnapshot(BaseModel):
    """One metadata revision (file / ai / accepted)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    is_current: bool
    title: str | None
    subtitle: str | None
    language: str | None
    series: str | None
    series_index: int | None
    isbn13: str | None
    confidence: float | None
    data: dict[str, Any]
    created_at: datetime


class FileDetail(BaseModel):
    """Single file with current `file` and `ai` metadata snapshots."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    directory_id: int
    filename: str
    extension: str | None
    format: str | None
    status: str
    sort_order: float | None
    error_message: str | None
    file_metadata: MetadataSnapshot | None
    ai_metadata: MetadataSnapshot | None


class EnrichmentTriggerResponse(BaseModel):
    """202 response from POST /api/files/{id}/enrich — exposes the new run id."""

    enrichment_run_id: int
    file_id: int
    status: str


class ProcessingLogEntry(BaseModel):
    """One entry from the processing log for a file."""

    model_config = ConfigDict(from_attributes=True)

    step: str
    level: str
    message: str
    duration_ms: int | None
    created_at: datetime


class ScanJobStatus(BaseModel):
    """Progress snapshot of a scan job."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    files_discovered: int
    files_processed: int
    current_filename: str | None
    error_message: str | None


DirectoryNode.model_rebuild()
