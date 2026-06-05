// Type-level drift gate for the @/types override layer. Checked by vue-tsc via
// tsconfig.contract.json (npm run type-check); a mismatch is a compile error.
import { expectTypeOf } from 'vitest'

import type { components } from '@/types/generated/openapi'
import type {
  DirectoryDetail,
  DirectoryNode,
  EnrichmentTriggerResponse,
  FileDetail,
  FileListItem,
  FileStatus,
  JsonValue,
  MetadataSnapshot,
  MetadataSource,
  PaginatedFiles,
  ScanJobState,
  ScanJobStatus,
} from '@/types'
import { FILE_STATUSES, SCAN_JOB_STATES } from '@/types'

type Schemas = components['schemas']

expectTypeOf<FileStatus>().toEqualTypeOf<Schemas['FileStatus']>()
expectTypeOf<(typeof FILE_STATUSES)[number]>().toEqualTypeOf<FileStatus>()

expectTypeOf<ScanJobState>().toEqualTypeOf<Schemas['ScanJobStatus']>()
expectTypeOf<(typeof SCAN_JOB_STATES)[number]>().toEqualTypeOf<ScanJobState>()

expectTypeOf<FileListItem['status']>().toEqualTypeOf<FileStatus>()
expectTypeOf<FileListItem['extension']>().toEqualTypeOf<string | null>()

expectTypeOf<DirectoryNode['children']>().toEqualTypeOf<DirectoryNode[]>()

expectTypeOf<DirectoryDetail['files']>().toEqualTypeOf<FileListItem[]>()
expectTypeOf<DirectoryDetail['id']>().toEqualTypeOf<Schemas['DirectoryDetail']['id']>()

expectTypeOf<ScanJobStatus>().toEqualTypeOf<Schemas['ScanJobProgress']>()
expectTypeOf<ScanJobStatus['status']>().toEqualTypeOf<ScanJobState>()

expectTypeOf<MetadataSnapshot['source']>().toEqualTypeOf<MetadataSource>()
expectTypeOf<MetadataSnapshot['data']>().toEqualTypeOf<Record<string, JsonValue>>()

expectTypeOf<FileDetail['file_metadata']>().toEqualTypeOf<MetadataSnapshot | null>()
expectTypeOf<FileDetail['ai_metadata']>().toEqualTypeOf<MetadataSnapshot | null>()
expectTypeOf<FileDetail['status']>().toEqualTypeOf<FileStatus>()

expectTypeOf<EnrichmentTriggerResponse['status']>().toEqualTypeOf<FileStatus>()

expectTypeOf<PaginatedFiles>().toEqualTypeOf<Schemas['PaginatedFiles']>()
expectTypeOf<PaginatedFiles['items']>().toEqualTypeOf<FileListItem[]>()
