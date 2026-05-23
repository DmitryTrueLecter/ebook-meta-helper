import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  acceptFile,
  apiFetch,
  enrichFile,
  getFileLogs,
  getFileMetadata,
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

describe('getFileMetadata', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('GETs /api/files/{id}/metadata and returns the payload', async () => {
    const payload = { file_id: 7, status: 'enriched', file: null, ai: null, accepted: null }
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({ status: 200, json: () => Promise.resolve(payload) }),
    )

    const result = await getFileMetadata(7)

    expect(result).toEqual(payload)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/files/7/metadata',
      expect.objectContaining({ headers: expect.any(Object) }),
    )
  })

  it('throws on 204 No Content (no silent null)', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(mockResponse({ status: 204, statusText: 'No Content' }))

    await expect(getFileMetadata(7)).rejects.toThrow(/empty response/)
  })

  it('propagates 500 errors with the backend detail', async () => {
    const fetchMock = vi.mocked(globalThis.fetch)
    fetchMock.mockResolvedValueOnce(
      mockResponse({
        status: 500,
        statusText: 'Internal Server Error',
        ok: false,
        json: () => Promise.resolve({ detail: 'metadata table missing' }),
      }),
    )

    await expect(getFileMetadata(7)).rejects.toThrow(/metadata table missing/)
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

describe('acceptFile / rejectFile / enrichFile', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const cases = [
    { name: 'acceptFile', fn: acceptFile, path: '/api/files/7/accept' },
    { name: 'rejectFile', fn: rejectFile, path: '/api/files/7/reject' },
    { name: 'enrichFile', fn: enrichFile, path: '/api/files/7/enrich' },
  ] as const

  it.each(cases)('$name POSTs to $path and returns the file payload', async ({ fn, path }) => {
    const payload = { file_id: 7, status: 'accepted', file: null, ai: null, accepted: null }
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
