import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  acceptFile,
  apiFetch,
  enrichFile,
  getDirectoryDetail,
  getFileDetail,
  getFileLogs,
  listDirectories,
  rejectFile,
  triggerDirectoryScan,
} from '@/services/api'

interface MockResponseInit {
  ok?: boolean
  status?: number
  statusText?: string
  json?: () => Promise<unknown>
  text?: () => Promise<string>
}

function mockResponse(init: MockResponseInit): Response {
  const status = init.status ?? 200
  return {
    ok: init.ok ?? (status >= 200 && status < 300),
    status,
    statusText: init.statusText ?? 'OK',
    json: init.json ?? (() => Promise.resolve({})),
    text: init.text ?? (() => Promise.resolve('')),
  } as unknown as Response
}

describe('apiFetch', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('returns parsed JSON for a 200 response', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve({ ok: true }) }),
    )

    const result = await apiFetch<{ ok: boolean }>('/x')

    expect(result).toEqual({ ok: true })
  })

  it('returns null for a 204 No Content response', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    const result = await apiFetch<unknown>('/x')

    expect(result).toBeNull()
  })

  it('throws an Error containing status and detail on a non-ok response', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'database down' }),
      }),
    )

    await expect(apiFetch('/x')).rejects.toThrow(/500.*database down/)
  })

  it('falls back to statusText when the error body is unparseable', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 502,
        statusText: 'Bad Gateway',
        ok: false,
        json: () => Promise.reject(new Error('not json')),
        text: () => Promise.reject(new Error('no body')),
      }),
    )

    await expect(apiFetch('/x')).rejects.toThrow(/502 Bad Gateway/)
  })

  it('sends JSON content-type header by default', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 200, json: () => Promise.resolve({}) }))

    await apiFetch('/x')

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined
    const headers = init?.headers as Record<string, string> | undefined
    expect(headers?.['Content-Type']).toBe('application/json')
  })
})

describe('listDirectories', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/directories and returns the array', async () => {
    const tree = [{ id: 1, name: 'root', children: [] }]
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(tree) }),
    )

    const result = await listDirectories()

    expect(result).toEqual(tree)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/directories',
      expect.objectContaining({ headers: expect.any(Object) }),
    )
  })

  it('throws on 204 No Content (does not silently return [])', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(listDirectories()).rejects.toThrow(/empty response/)
  })

  it('propagates network errors', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockRejectedValueOnce(new Error('network down'))

    await expect(listDirectories()).rejects.toThrow(/network down/)
  })
})

describe('getDirectoryDetail', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/directories/{id} without filter when none given', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve({ id: 7, files: [] }) }),
    )

    await getDirectoryDetail(7)

    expect(fetchMock).toHaveBeenCalledWith('/api/directories/7', expect.any(Object))
  })

  it('appends ?status=<filter> when filter is given', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve({ id: 7, files: [] }) }),
    )

    await getDirectoryDetail(7, 'accepted')

    expect(fetchMock).toHaveBeenCalledWith('/api/directories/7?status=accepted', expect.any(Object))
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(getDirectoryDetail(7)).rejects.toThrow(/empty response/)
  })
})

describe('triggerDirectoryScan', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs /api/directories/{id}/scan and returns the job', async () => {
    const job = { id: 1, status: 'queued', files_discovered: 0, files_processed: 0, current_filename: null }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 202, json: () => Promise.resolve(job) }),
    )

    const result = await triggerDirectoryScan(42)

    expect(result).toEqual(job)
    const call = fetchMock.mock.calls[0]
    expect(call?.[0]).toBe('/api/directories/42/scan')
    expect((call?.[1] as RequestInit | undefined)?.method).toBe('POST')
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(triggerDirectoryScan(42)).rejects.toThrow(/empty response/)
  })

  it('throws on 500 with backend detail message', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'scan worker offline' }),
      }),
    )

    await expect(triggerDirectoryScan(42)).rejects.toThrow(/scan worker offline/)
  })
})

describe('getFileDetail', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/files/{id} and returns the payload', async () => {
    const payload = {
      id: 7,
      directory_id: 1,
      filename: 'book.epub',
      extension: '.epub',
      format: 'epub',
      status: 'enriched',
      sort_order: 1.0,
      error_message: null,
      file_metadata: null,
      ai_metadata: null,
    }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(payload) }),
    )

    const result = await getFileDetail(7)

    expect(result).toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/files/7',
      expect.objectContaining({ headers: expect.any(Object) }),
    )
  })

  it('throws on 204 No Content (no silent null)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(getFileDetail(7)).rejects.toThrow(/empty response/)
  })

  it('propagates 500 errors with the backend detail', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'file table missing' }),
      }),
    )

    await expect(getFileDetail(7)).rejects.toThrow(/file table missing/)
  })
})

describe('getFileLogs', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/files/{id}/logs and returns the array', async () => {
    const logs = [
      { step: 'read', level: 'info', message: 'ok', duration_ms: 10, created_at: '2026-05-23T00:00:00Z' },
    ]
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(logs) }),
    )

    const result = await getFileLogs(7)

    expect(result).toEqual(logs)
    expect(fetchMock).toHaveBeenCalledWith('/api/files/7/logs', expect.any(Object))
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(getFileLogs(7)).rejects.toThrow(/empty response/)
  })
})

describe('acceptFile / rejectFile', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const cases = [
    { name: 'acceptFile', fn: acceptFile, path: '/api/files/7/accept' },
    { name: 'rejectFile', fn: rejectFile, path: '/api/files/7/reject' },
  ] as const

  it.each(cases)('$name POSTs to $path and returns the FileListItem payload', async ({ fn, path }) => {
    const payload = {
      id: 7,
      filename: 'book.epub',
      extension: '.epub',
      format: 'epub',
      status: 'accepted',
      has_ai_suggestion: true,
      sort_order: 1.0,
    }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(payload) }),
    )

    const result = await fn(7)

    expect(result).toEqual(payload)
    const call = fetchMock.mock.calls[0]
    expect(call?.[0]).toBe(path)
    expect((call?.[1] as RequestInit | undefined)?.method).toBe('POST')
  })

  it.each(cases)('$name throws on 204 No Content', async ({ fn }) => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(fn(7)).rejects.toThrow(/empty response/)
  })

  it.each(cases)('$name propagates backend errors', async ({ fn }) => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'pipeline broken' }),
      }),
    )

    await expect(fn(7)).rejects.toThrow(/pipeline broken/)
  })
})

describe('enrichFile', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs to /api/files/{id}/enrich and returns the EnrichmentTriggerResponse', async () => {
    const payload = { enrichment_run_id: 42, file_id: 7, status: 'ai_queued' }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 202, json: () => Promise.resolve(payload) }),
    )

    const result = await enrichFile(7)

    expect(result).toEqual(payload)
    const call = fetchMock.mock.calls[0]
    expect(call?.[0]).toBe('/api/files/7/enrich')
    expect((call?.[1] as RequestInit | undefined)?.method).toBe('POST')
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(enrichFile(7)).rejects.toThrow(/empty response/)
  })

  it('propagates backend errors', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'queue broken' }),
      }),
    )

    await expect(enrichFile(7)).rejects.toThrow(/queue broken/)
  })
})
