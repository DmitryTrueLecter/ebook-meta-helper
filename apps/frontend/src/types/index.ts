// Override/refinement layer over the machine-generated OpenAPI base.
// Canonical import surface for the app (`@/types`); never edit generated/.
import type { components } from './generated/openapi'

type Schemas = components['schemas']

// Runtime list — drives stable UI ordering; FileStatus below is asserted equal to the generated enum.
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

export type FileStatus = Schemas['FileStatus']

// Runtime list mirroring the backend ScanJobStatus enum, in emit order.
export const SCAN_JOB_STATES = [
  'pending',
  'running',
  'done',
  'failed',
  'cancelled',
] as const

export type ScanJobState = Schemas['ScanJobStatus']

// children is optional in the base schema but the tree endpoint always emits it.
export interface DirectoryNode extends Omit<Schemas['DirectoryNode'], 'children'> {
  children: DirectoryNode[]
}

// status is already the FileStatus enum and extension already nullable in the base.
export type FileListItem = Schemas['FileListItem']

// files is optional in the base schema but every directory-detail response carries it.
export type DirectoryDetail = Omit<Schemas['DirectoryDetail'], 'files'> & {
  files: FileListItem[]
}

// Backend schema is named ScanJobProgress; app preserves the original ScanJobStatus name for UI compatibility.
export type ScanJobStatus = Schemas['ScanJobProgress']

export type MetadataSource = 'file' | 'ai' | 'accepted'

// Keeps MetadataSnapshot.data (authors/tags/description/...) typed without `any`.
export type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue }

// Backend types source as `str` and data as an open object; narrow both on the frontend.
export type MetadataSnapshot = Omit<Schemas['MetadataSnapshot'], 'source' | 'data'> & {
  source: MetadataSource
  data: Record<string, JsonValue>
}

// Re-narrow the snapshot fields to the refined MetadataSnapshot above.
export type FileDetail = Omit<Schemas['FileDetail'], 'file_metadata' | 'ai_metadata'> & {
  file_metadata: MetadataSnapshot | null
  ai_metadata: MetadataSnapshot | null
}

// status already references the FileStatus enum in the base.
export type EnrichmentTriggerResponse = Schemas['EnrichmentTriggerResponse']

export type ProcessingLogEntry = Schemas['ProcessingLogEntry']

export type PaginatedFiles = Schemas['PaginatedFiles']
