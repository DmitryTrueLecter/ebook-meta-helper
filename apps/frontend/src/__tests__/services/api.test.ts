import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  apiFetch,
  getDirectoryDetail,
  listDirectories,
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

  it('falls back to statusText when error body is unparseable', async () => {
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
