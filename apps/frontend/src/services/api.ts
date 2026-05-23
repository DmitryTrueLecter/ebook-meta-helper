import type { FileMetadataResponse, ProcessingLogEntry } from '@/types'

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

// GET /api/files/{id}/metadata — current snapshots (file / ai / accepted) for one file.
export async function getFileMetadata(id: number): Promise<FileMetadataResponse> {
  const metadata = await apiFetch<FileMetadataResponse>(`/files/${id}/metadata`)
  if (metadata === null) {
    throw new Error(`File ${id} metadata returned an empty response`)
  }
  return metadata
}

// GET /api/files/{id}/logs — full processing history, oldest first.
export async function getFileLogs(id: number): Promise<ProcessingLogEntry[]> {
  const logs = await apiFetch<ProcessingLogEntry[]>(`/files/${id}/logs`)
  if (logs === null) {
    throw new Error(`File ${id} logs returned an empty response`)
  }
  return logs
}

// POST /api/files/{id}/accept — persist current AI snapshot as the accepted revision.
export async function acceptFile(id: number): Promise<FileMetadataResponse> {
  const result = await apiFetch<FileMetadataResponse>(`/files/${id}/accept`, { method: 'POST' })
  if (result === null) {
    throw new Error(`Accept on file ${id} returned an empty response`)
  }
  return result
}

// POST /api/files/{id}/reject — mark the AI snapshot as rejected; status becomes `rejected`.
export async function rejectFile(id: number): Promise<FileMetadataResponse> {
  const result = await apiFetch<FileMetadataResponse>(`/files/${id}/reject`, { method: 'POST' })
  if (result === null) {
    throw new Error(`Reject on file ${id} returned an empty response`)
  }
  return result
}

// POST /api/files/{id}/enrich — re-queue AI enrichment; status flips to `ai_queued`.
export async function enrichFile(id: number): Promise<FileMetadataResponse> {
  const result = await apiFetch<FileMetadataResponse>(`/files/${id}/enrich`, { method: 'POST' })
  if (result === null) {
    throw new Error(`Enrich on file ${id} returned an empty response`)
  }
  return result
}
