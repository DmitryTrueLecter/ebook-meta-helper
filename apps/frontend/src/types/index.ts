// TypeScript interfaces mirroring backend Pydantic schemas.

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

// GET /api/files/{id}/metadata — current snapshots per source; any source may be null when not yet produced.
export interface FileMetadataResponse {
  file_id: number
  status: FileStatus
  file: MetadataSnapshot | null
  ai: MetadataSnapshot | null
  accepted: MetadataSnapshot | null
}

// Mirrors apps/backend/app/api/schemas.py:ProcessingLogEntry.
export interface ProcessingLogEntry {
  step: string
  level: string
  message: string
  duration_ms: number | null
  created_at: string
}
