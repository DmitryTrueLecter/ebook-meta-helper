// TypeScript interfaces mirroring backend Pydantic schemas.

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
