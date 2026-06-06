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

// Carries the HTTP status so callers can branch on it (e.g. 404 → "no resource").
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, statusText: string, detail: string) {
    super(`${status} ${statusText}: ${detail}`)
    this.name = 'ApiError'
    this.status = status
  }
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
    throw new ApiError(response.status, response.statusText, detail)
  }

  if (response.status === 204) {
    return null
  }

  return (await response.json()) as T
}

// GET /api/directories — full tree, roots first. Archived (missing) dirs hidden unless includeMissing.
export async function listDirectories(includeMissing = false): Promise<DirectoryNode[]> {
  const query = includeMissing ? '?include_missing=true' : ''
  const tree = await apiFetch<DirectoryNode[]>(`/directories${query}`)
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

// POST /api/directories/{id}/discover — FS↔DB sync + read metadata (no AI); returns 202 + job status.
export async function discoverDirectory(id: number): Promise<ScanJobStatus> {
  const job = await apiFetch<ScanJobStatus>(`/directories/${id}/discover`, {
    method: 'POST',
  })
  if (job === null) {
    throw new Error(`Discover trigger for directory ${id} returned an empty response`)
  }
  return job
}

// GET /api/scan/status — null when no scan is active (404 from the backend, or 204).
export async function getScanStatus(): Promise<ScanJobStatus | null> {
  try {
    return await apiFetch<ScanJobStatus>('/scan/status')
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null
    }
    throw err
  }
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
