import type {
  DirectoryDetail,
  DirectoryNode,
  EnrichmentTriggerResponse,
  FileDetail,
  FileListItem,
  FileStatus,
  ProcessingLogEntry,
  ScanJobStatus,
} from '@/types'

const API_BASE = '/api'

export interface ApiFetchOptions extends RequestInit {
  headers?: Record<string, string>
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T | null> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
  })

  if (!response.ok) {
    let detail: string = response.statusText
    try {
      const body = (await response.json()) as { detail?: string }
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      try {
        detail = await response.text()
      } catch {
        // empty/unparseable body — keep statusText
      }
    }
    throw new Error(`${response.status} ${response.statusText}: ${detail}`)
  }

  if (response.status === 204) {
    return null
  }

  return (await response.json()) as T
}

// GET /api/directories — full tree, roots first.
export async function listDirectories(): Promise<DirectoryNode[]> {
  const tree = await apiFetch<DirectoryNode[]>('/directories')
  if (tree === null) {
    throw new Error('Directories listing returned an empty response')
  }
  return tree
}

// GET /api/directories/{id} — directory + its files. Optional status filter.
export async function getDirectoryDetail(
  id: number,
  statusFilter?: FileStatus,
): Promise<DirectoryDetail> {
  const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : ''
  const detail = await apiFetch<DirectoryDetail>(`/directories/${id}${query}`)
  if (detail === null) {
    throw new Error(`Directory ${id} returned an empty response`)
  }
  return detail
}

// POST /api/directories/{id}/scan — enqueue scan, returns 202 + scan-job status.
export async function triggerDirectoryScan(id: number): Promise<ScanJobStatus> {
  const job = await apiFetch<ScanJobStatus>(`/directories/${id}/scan`, {
    method: 'POST',
  })
  if (job === null) {
    throw new Error(`Scan trigger for directory ${id} returned an empty response`)
  }
  return job
}

// GET /api/files/{id} — single file with current `file_metadata` and `ai_metadata` snapshots.
export async function getFileDetail(id: number): Promise<FileDetail> {
  const detail = await apiFetch<FileDetail>(`/files/${id}`)
  if (detail === null) {
    throw new Error(`File ${id} detail returned an empty response`)
  }
  return detail
}

// GET /api/files/{id}/logs — last N processing-log entries for the file, newest first.
export async function getFileLogs(id: number): Promise<ProcessingLogEntry[]> {
  const logs = await apiFetch<ProcessingLogEntry[]>(`/files/${id}/logs`)
  if (logs === null) {
    throw new Error(`File ${id} logs returned an empty response`)
  }
  return logs
}

// POST /api/files/{id}/accept — apply the AI suggestion; returns the updated FileListItem.
export async function acceptFile(id: number): Promise<FileListItem> {
  const result = await apiFetch<FileListItem>(`/files/${id}/accept`, { method: 'POST' })
  if (result === null) {
    throw new Error(`Accept on file ${id} returned an empty response`)
  }
  return result
}

// POST /api/files/{id}/reject — mark the file as rejected; returns the updated FileListItem.
export async function rejectFile(id: number): Promise<FileListItem> {
  const result = await apiFetch<FileListItem>(`/files/${id}/reject`, { method: 'POST' })
  if (result === null) {
    throw new Error(`Reject on file ${id} returned an empty response`)
  }
  return result
}

// POST /api/files/{id}/enrich — queue re-enrichment; returns the EnrichmentTriggerResponse (202).
export async function enrichFile(id: number): Promise<EnrichmentTriggerResponse> {
  const result = await apiFetch<EnrichmentTriggerResponse>(`/files/${id}/enrich`, {
    method: 'POST',
  })
  if (result === null) {
    throw new Error(`Enrich on file ${id} returned an empty response`)
  }
  return result
}
