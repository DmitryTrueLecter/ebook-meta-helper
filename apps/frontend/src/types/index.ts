// TypeScript interfaces mirroring backend Pydantic schemas
// (apps/backend/app/api/schemas.py).

export interface ApiError {
  detail: string
}

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

// Backend FileListItem — returned by file listings and accept/reject endpoints.
export interface FileListItem {
  id: number
  filename: string
  extension: string | null
  format: string | null
  status: FileStatus
  has_ai_suggestion: boolean
  sort_order: number | null
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
