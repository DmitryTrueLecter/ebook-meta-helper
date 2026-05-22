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
  extension: string | null
  format: string | null
  status: FileStatus
  has_ai_suggestion: boolean
  sort_order: number | null
}

// Mirrors apps/backend/app/api/schemas.py:DirectoryDetail.
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

// Mirrors apps/backend/app/api/schemas.py:ScanJobStatus.
export interface ScanJobStatus {
  id: number
  status: string
  files_discovered: number
  files_processed: number
  current_filename: string | null
}
