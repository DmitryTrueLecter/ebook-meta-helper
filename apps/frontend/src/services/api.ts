import type {
  DirectoryDetail,
  DirectoryNode,
  FileStatus,
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
