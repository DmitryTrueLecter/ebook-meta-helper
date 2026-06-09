"""Pydantic response schemas for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from db.models.directory import DirectoryStatus
from db.models.file_record import FileStatus
from db.models.scan_job import ScanJobStatus


class DirectoryNode(BaseModel):
    """Directory tree node with aggregated file counts and nested children."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    path: str
    depth: int
    status: DirectoryStatus
    file_count: int
    pending_count: int
    enriched_count: int
    accepted_count: int
    missing_count: int
    children: list[DirectoryNode] = Field(default_factory=list)


class FileListItem(BaseModel):
    """One row in a file listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    extension: str | None
    format: str | None
    status: FileStatus
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
    status: FileStatus
    sort_order: float | None
    error_message: str | None
    file_metadata: MetadataSnapshot | None
    ai_metadata: MetadataSnapshot | None


class EnrichmentTriggerResponse(BaseModel):
    """202 response from POST /api/files/{id}/enrich — exposes the new run id."""

    enrichment_run_id: int
    file_id: int
    status: FileStatus


class ProcessingLogEntry(BaseModel):
    """One entry from the processing log for a file."""

    model_config = ConfigDict(from_attributes=True)

    step: str
    level: str
    message: str
    duration_ms: int | None
    created_at: datetime


class AICallSummary(BaseModel):
    """One AI call as a list row — identity, tier, and cost metrics; no prompt/response text."""

    id: int
    file_id: int
    enrichment_run_id: int | None
    sequence: int
    tier: str
    is_canonical: bool
    model: str
    confidence: float | None
    prompt_tokens: int | None
    completion_tokens: int | None
    cost_usd: float | None
    duration_ms: int
    created_at: datetime


class AICallDetail(AICallSummary):
    """Full AI call — summary fields plus the prompts, raw response, and provenance."""

    system_prompt: str
    user_prompt: str
    raw_response: str
    response_format_ref: str
    effort: str | None
    parse_errors: Any | None
    origin: str
    config_version_id: int | None


class AIConfigVersionView(BaseModel):
    """One versioned AI runtime configuration row."""

    id: int
    version: int
    label: str | None
    system_prompt: str
    cheap_model: str
    expensive_model: str
    effort: str
    escalation_threshold: float
    provider: str
    response_format_ref: str
    is_active: bool
    created_at: datetime
    created_by: str | None


class ScanJobProgress(BaseModel):
    """Progress snapshot of a scan job."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    status: ScanJobStatus
    files_discovered: int
    files_processed: int
    current_filename: str | None
    error_message: str | None


DirectoryNode.model_rebuild()
