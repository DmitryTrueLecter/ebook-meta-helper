// TypeScript interfaces mirroring backend Pydantic schemas
// (apps/backend/app/api/schemas.py).

// Mirrors db.models.file_record.FileStatus.
// Order matches the backend enum so iteration produces a stable UI order.
export const FILE_STATUSES = [
  'pending',
  'reading',
  'ai_queued',
  'enriching',
  'enriched',
  'accepted',
  'rejected',
  'failed',
] as const

export type FileStatus = (typeof FILE_STATUSES)[number]

// Mirrors apps/backend/app/api/schemas.py:DirectoryNode.
export interface DirectoryNode {
  id: number
  name: string
  path: string
  depth: number
  file_count: number
  pending_count: number
  enriched_count: number
  accepted_count: number
  children: DirectoryNode[]
}

// Mirrors apps/backend/app/api/schemas.py:FileListItem.
export interface FileListItem {
  id: number
  filename: string
  extension: string
  format: string | null
  status: FileStatus
  has_ai_suggestion: boolean
  sort_order: number | null
}

// Frontend-only composition: GET /api/directories/{id} has no backend Pydantic schema yet.
export interface DirectoryDetail {
  id: number
  name: string
  path: string
  depth: number
  file_count: number
  pending_count: number
  enriched_count: number
  accepted_count: number
  files: FileListItem[]
}

// Mirrors apps.backend.db.models.scan_job.ScanJobStatus.
// Order matches the backend enum.
export const SCAN_JOB_STATES = [
  'pending',
  'running',
  'done',
  'failed',
  'cancelled',
] as const

export type ScanJobState = (typeof SCAN_JOB_STATES)[number]

// Mirrors apps/backend/app/api/schemas.py:ScanJobStatus.
// Backend declares `status: str`; we narrow it to the enum the model emits.
export interface ScanJobStatus {
  id: number
  status: ScanJobState
  files_discovered: number
  files_processed: number
  current_filename: string | null
}

// JsonValue keeps the MetadataSnapshot.data dict (authors/tags/description/...) typed without `any`.
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

export type MetadataSource = 'file' | 'ai' | 'accepted'

export interface MetadataSnapshot {
  id: number
  source: MetadataSource
  is_current: boolean
  title: string | null
  subtitle: string | null
  language: string | null
  series: string | null
  series_index: number | null
  isbn13: string | null
  confidence: number | null
  data: Record<string, JsonValue>
  created_at: string
}

// GET /api/files/{id} — single file with current file/ai metadata snapshots.
export interface FileDetail {
  id: number
  directory_id: number
  filename: string
  extension: string | null
  format: string | null
  status: FileStatus
  sort_order: number | null
  error_message: string | null
  file_metadata: MetadataSnapshot | null
  ai_metadata: MetadataSnapshot | null
}

// 202 response from POST /api/files/{id}/enrich.
export interface EnrichmentTriggerResponse {
  enrichment_run_id: number
  file_id: number
  status: FileStatus
}

// Mirrors apps/backend/app/api/schemas.py:ProcessingLogEntry.
export interface ProcessingLogEntry {
  step: string
  level: string
  message: string
  duration_ms: number | null
  created_at: string
}
