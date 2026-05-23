import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import FileDetailPage from '@/pages/FileDetailPage.vue'
import * as api from '@/services/api'
import type { FileMetadataResponse, MetadataSnapshot, ProcessingLogEntry } from '@/types'

function fileSnapshot(overrides: Partial<MetadataSnapshot> = {}): MetadataSnapshot {
  return {
    id: 1,
    source: 'file',
    is_current: true,
    title: 'Original Title',
    subtitle: null,
    language: 'en',
    series: null,
    series_index: null,
    isbn13: null,
    confidence: null,
    data: { authors: ['Asimov'] },
    created_at: '2026-05-23T00:00:00Z',
    ...overrides,
  }
}

function aiSnapshot(overrides: Partial<MetadataSnapshot> = {}): MetadataSnapshot {
  return {
    id: 2,
    source: 'ai',
    is_current: true,
    title: 'New Title',
    subtitle: null,
    language: 'en',
    series: 'Foundation',
    series_index: 1,
    isbn13: null,
    confidence: 0.95,
    data: { authors: ['Isaac Asimov'], tags: ['scifi'], description: 'A novel.' },
    created_at: '2026-05-23T00:01:00Z',
    ...overrides,
  }
}

function metadataResponse(overrides: Partial<FileMetadataResponse> = {}): FileMetadataResponse {
  return {
    file_id: 7,
    status: 'enriched',
    file: fileSnapshot(),
    ai: aiSnapshot(),
    accepted: null,
    ...overrides,
  }
}

function logEntry(overrides: Partial<ProcessingLogEntry> = {}): ProcessingLogEntry {
  return {
    step: 'read_metadata',
    level: 'info',
    message: 'parsed cover',
    duration_ms: 12,
    created_at: '2026-05-23T10:00:00Z',
    ...overrides,
  }
}

async function mountAt(routerInstance: Router, path: string) {
  await routerInstance.push(path)
  await routerInstance.isReady()
  return mount(FileDetailPage, { global: { plugins: [routerInstance] } })
}

function buildTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/files/:id(\\d+)', name: 'file-detail', component: FileDetailPage },
      { path: '/files/:id', name: 'file-detail-loose', component: FileDetailPage },
    ],
  })
}

describe('FileDetailPage — data fetching', () => {
  let testRouter: Router

  beforeEach(() => {
    testRouter = buildTestRouter()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls getFileMetadata with the route id on mount', async () => {
    const spy = vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())

    await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(spy).toHaveBeenCalledOnce()
    expect(spy).toHaveBeenCalledWith(7)
  })

  it('shows the loading message while the metadata fetch is in flight', async () => {
    let resolveMetadata: ((value: FileMetadataResponse) => void) | null = null
    vi.spyOn(api, 'getFileMetadata').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveMetadata = resolve
        }),
    )

    const wrapper = await mountAt(testRouter, '/files/7')

    expect(wrapper.text()).toContain('Loading metadata')

    resolveMetadata!(metadataResponse())
    await flushPromises()

    expect(wrapper.text()).not.toContain('Loading metadata')
  })

  it('renders both diff panels when metadata loads with file + ai snapshots', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(wrapper.text()).toContain('Original (file)')
    expect(wrapper.text()).toContain('AI suggestion')
    expect(wrapper.text()).toContain('Original Title')
    expect(wrapper.text()).toContain('New Title')
  })

  it('shows the empty placeholder on the AI panel when ai is null', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(
      metadataResponse({ ai: null, status: 'pending' }),
    )

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(wrapper.text()).toContain('AI has not produced a suggestion yet')
  })

  it('shows the empty placeholder on the file panel when file is null', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(
      metadataResponse({ file: null, status: 'pending' }),
    )

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(wrapper.text()).toContain('No metadata read from file yet')
  })

  it('shows an error message when getFileMetadata rejects', async () => {
    vi.spyOn(api, 'getFileMetadata').mockRejectedValue(new Error('500 Internal Server Error'))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(wrapper.text()).toContain('500 Internal Server Error')
  })

  it('rejects an invalid (non-numeric) id by showing the invalid-id message', async () => {
    const spy = vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())

    await testRouter.push('/files/abc')
    await testRouter.isReady()
    const wrapper = mount(FileDetailPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid file id')
    expect(spy).not.toHaveBeenCalled()
  })
})

describe('FileDetailPage — diff highlighting visible in the rendered DOM', () => {
  let testRouter: Router

  beforeEach(() => {
    testRouter = buildTestRouter()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('applies yellow highlight when AI changes a field', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(
      metadataResponse({
        file: fileSnapshot({ title: 'Old' }),
        ai: aiSnapshot({ title: 'New' }),
      }),
    )

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(wrapper.html()).toContain('bg-yellow-100')
  })

  it('applies green highlight when AI introduces a new field that was empty in the file', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(
      metadataResponse({
        file: fileSnapshot({ series: null }),
        ai: aiSnapshot({ series: 'Foundation' }),
      }),
    )

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(wrapper.html()).toContain('bg-green-100')
  })
})

describe('FileDetailPage — actions', () => {
  let testRouter: Router

  beforeEach(() => {
    testRouter = buildTestRouter()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('Accept calls acceptFile with the route id and updates the status badge from the response', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    const acceptSpy = vi
      .spyOn(api, 'acceptFile')
      .mockResolvedValue(metadataResponse({ status: 'accepted' }))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const buttons = wrapper.findAll('button')
    const acceptBtn = buttons.find((b) => b.text().includes('Accept'))
    expect(acceptBtn).toBeDefined()
    await acceptBtn!.trigger('click')
    await flushPromises()

    expect(acceptSpy).toHaveBeenCalledWith(7)
    expect(wrapper.text()).toContain('Accepted AI suggestion')
    expect(wrapper.text()).toContain('accepted')
  })

  it('Reject calls rejectFile and shows the reject toast', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    const rejectSpy = vi
      .spyOn(api, 'rejectFile')
      .mockResolvedValue(metadataResponse({ status: 'rejected' }))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const rejectBtn = wrapper.findAll('button').find((b) => b.text().includes('Reject'))
    await rejectBtn!.trigger('click')
    await flushPromises()

    expect(rejectSpy).toHaveBeenCalledWith(7)
    expect(wrapper.text()).toContain('Rejected AI suggestion')
  })

  it('Re-run AI calls enrichFile and shows the queued toast', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    const enrichSpy = vi
      .spyOn(api, 'enrichFile')
      .mockResolvedValue(metadataResponse({ status: 'ai_queued' }))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const enrichBtn = wrapper.findAll('button').find((b) => b.text().includes('Re-run AI'))
    await enrichBtn!.trigger('click')
    await flushPromises()

    expect(enrichSpy).toHaveBeenCalledWith(7)
    expect(wrapper.text()).toContain('Re-running AI enrichment')
  })

  it('shows the error toast when an action rejects (does not crash)', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    vi.spyOn(api, 'acceptFile').mockRejectedValue(new Error('500 backend down'))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const acceptBtn = wrapper.findAll('button').find((b) => b.text().includes('Accept'))
    await acceptBtn!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('500 backend down')
  })

  it('disables Accept and Reject when the status is already accepted (terminal)', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse({ status: 'accepted' }))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const acceptBtn = wrapper.findAll('button').find((b) => b.text().trim().startsWith('Accept'))
    const rejectBtn = wrapper.findAll('button').find((b) => b.text().trim().startsWith('Reject'))
    const enrichBtn = wrapper.findAll('button').find((b) => b.text().includes('Re-run AI'))

    expect(acceptBtn?.attributes('disabled')).toBeDefined()
    expect(rejectBtn?.attributes('disabled')).toBeDefined()
    // Re-run is always available.
    expect(enrichBtn?.attributes('disabled')).toBeUndefined()
  })

  it('disables Accept and Reject when there is no AI snapshot yet', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(
      metadataResponse({ ai: null, status: 'pending' }),
    )

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const acceptBtn = wrapper.findAll('button').find((b) => b.text().trim().startsWith('Accept'))
    const rejectBtn = wrapper.findAll('button').find((b) => b.text().trim().startsWith('Reject'))

    expect(acceptBtn?.attributes('disabled')).toBeDefined()
    expect(rejectBtn?.attributes('disabled')).toBeDefined()
  })
})

describe('FileDetailPage — processing log', () => {
  let testRouter: Router

  beforeEach(() => {
    testRouter = buildTestRouter()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('does not fetch logs until the section is expanded', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    const logsSpy = vi.spyOn(api, 'getFileLogs').mockResolvedValue([])

    await mountAt(testRouter, '/files/7')
    await flushPromises()

    expect(logsSpy).not.toHaveBeenCalled()
  })

  it('fetches logs the first time the section is expanded', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    const logsSpy = vi.spyOn(api, 'getFileLogs').mockResolvedValue([logEntry()])

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const toggle = wrapper.findAll('button').find((b) => b.text().includes('Show processing log'))
    await toggle!.trigger('click')
    await flushPromises()

    expect(logsSpy).toHaveBeenCalledWith(7)
    expect(wrapper.text()).toContain('parsed cover')
  })

  it('shows the empty-log message when the backend returns no entries', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    vi.spyOn(api, 'getFileLogs').mockResolvedValue([])

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const toggle = wrapper.findAll('button').find((b) => b.text().includes('Show processing log'))
    await toggle!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('No processing log entries yet')
  })

  it('shows an error message when the log fetch fails', async () => {
    vi.spyOn(api, 'getFileMetadata').mockResolvedValue(metadataResponse())
    vi.spyOn(api, 'getFileLogs').mockRejectedValue(new Error('500 logs unavailable'))

    const wrapper = await mountAt(testRouter, '/files/7')
    await flushPromises()

    const toggle = wrapper.findAll('button').find((b) => b.text().includes('Show processing log'))
    await toggle!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('500 logs unavailable')
  })
})
