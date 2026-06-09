import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  acceptFile,
  ApiError,
  apiFetch,
  discoverDirectory,
  enrichFile,
  getActiveAiConfig,
  getAiCallDetail,
  getDirectoryDetail,
  getFileDetail,
  getFileLogs,
  getScanStatus,
  listAiConfigVersions,
  listDirectories,
  listFileAiCalls,
  rejectFile,
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

  it('throws an ApiError with the HTTP status on a non-ok response', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 404,
        statusText: 'Not Found',
        ok: false,
        json: () => Promise.resolve({ detail: 'nope' }),
      }),
    )

    let thrown: unknown = null
    try {
      await apiFetch('/x')
    } catch (err) {
      thrown = err
    }

    expect(thrown).toBeInstanceOf(ApiError)
    expect((thrown as ApiError).status).toBe(404)
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

describe('discoverDirectory', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('POSTs /api/directories/{id}/discover and returns the job', async () => {
    const job = { id: 1, status: 'queued', files_discovered: 0, files_processed: 0, current_filename: null }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 202, json: () => Promise.resolve(job) }),
    )

    const result = await discoverDirectory(42)

    expect(result).toEqual(job)
    const call = fetchMock.mock.calls[0]
    expect(call?.[0]).toBe('/api/directories/42/discover')
    expect((call?.[1] as RequestInit | undefined)?.method).toBe('POST')
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(discoverDirectory(42)).rejects.toThrow(/empty response/)
  })

  it('throws on 500 with backend detail message', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'discover worker offline' }),
      }),
    )

    await expect(discoverDirectory(42)).rejects.toThrow(/discover worker offline/)
  })
})

describe('getScanStatus', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/scan/status and returns the job when one is active', async () => {
    const job = {
      id: 5,
      status: 'running',
      files_discovered: 100,
      files_processed: 42,
      current_filename: 'a.epub',
    }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(job) }),
    )

    const result = await getScanStatus()

    expect(result).toEqual(job)
    expect(fetchMock).toHaveBeenCalledWith('/api/scan/status', expect.any(Object))
  })

  it('returns null on 404 (no active scan)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 404,
        statusText: 'Not Found',
        ok: false,
        json: () => Promise.resolve({ detail: 'no active scan' }),
      }),
    )

    const result = await getScanStatus()

    expect(result).toBeNull()
  })

  it('returns null on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 204, statusText: 'No Content' }),
    )

    const result = await getScanStatus()

    expect(result).toBeNull()
  })

  it('throws on 500 (real error — not silently masked as null)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'boom' }),
      }),
    )

    await expect(getScanStatus()).rejects.toThrow(/500.*boom/)
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

describe('listFileAiCalls', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/files/{id}/ai-calls and returns the array', async () => {
    const calls = [{ id: 1, file_id: 7, sequence: 1, tier: 'cheap' }]
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(calls) }),
    )

    const result = await listFileAiCalls(7)

    expect(result).toEqual(calls)
    expect(fetchMock).toHaveBeenCalledWith('/api/files/7/ai-calls', expect.any(Object))
  })

  it('throws on 204 No Content (no silent empty array)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(listFileAiCalls(7)).rejects.toThrow(/empty response/)
  })

  it('propagates backend errors', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'ai_call table missing' }),
      }),
    )

    await expect(listFileAiCalls(7)).rejects.toThrow(/ai_call table missing/)
  })
})

describe('getAiCallDetail', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/ai-calls/{id} and returns the payload', async () => {
    const payload = { id: 2, file_id: 7, sequence: 2, tier: 'expensive', system_prompt: 'sp' }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(payload) }),
    )

    const result = await getAiCallDetail(2)

    expect(result).toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith('/api/ai-calls/2', expect.any(Object))
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(getAiCallDetail(2)).rejects.toThrow(/empty response/)
  })
})

describe('getActiveAiConfig', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/ai-config/active and returns the config when one is active', async () => {
    const payload = { id: 5, version: 3, is_active: true }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(payload) }),
    )

    const result = await getActiveAiConfig()

    expect(result).toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith('/api/ai-config/active', expect.any(Object))
  })

  it('returns null on 404 (no active config)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 404,
        statusText: 'Not Found',
        ok: false,
        json: () => Promise.resolve({ detail: 'no active config' }),
      }),
    )

    const result = await getActiveAiConfig()

    expect(result).toBeNull()
  })

  it('throws on 500 (real error — not masked as null)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'config table broken' }),
      }),
    )

    await expect(getActiveAiConfig()).rejects.toThrow(/config table broken/)
  })
})

describe('listAiConfigVersions', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/ai-config/versions and returns the array', async () => {
    const versions = [{ id: 5, version: 3 }, { id: 4, version: 2 }]
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(versions) }),
    )

    const result = await listAiConfigVersions()

    expect(result).toEqual(versions)
    expect(fetchMock).toHaveBeenCalledWith('/api/ai-config/versions', expect.any(Object))
  })

  it('throws on 204 No Content', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(listAiConfigVersions()).rejects.toThrow(/empty response/)
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
