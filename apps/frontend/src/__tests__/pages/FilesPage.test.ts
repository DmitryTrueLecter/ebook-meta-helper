import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import FilesPage from '@/pages/FilesPage.vue'
import * as api from '@/services/api'
import type { DirectoryDetail, FileListItem } from '@/types'

function makeFile(overrides: Partial<FileListItem> = {}): FileListItem {
  return {
    id: 1,
    filename: 'book.epub',
    extension: 'epub',
    format: 'EPUB',
    status: 'pending',
    has_ai_suggestion: false,
    sort_order: 1,
    ...overrides,
  }
}

function makeDirectoryDetail(files: FileListItem[]): DirectoryDetail {
  return {
    id: 42,
    name: 'fiction',
    path: '/lib/fiction',
    depth: 1,
    file_count: files.length,
    pending_count: 0,
    enriched_count: 0,
    accepted_count: 0,
    files,
  }
}

function buildTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/directories', name: 'directories', component: { template: '<div />' } },
      { path: '/directories/:id/files', name: 'files', component: FilesPage },
      { path: '/files/:id', name: 'file-detail', component: { template: '<div />' } },
      { path: '/scan', name: 'scan', component: { template: '<div />' } },
    ],
  })
}

async function mountAtFilesRoute(directoryId = 42) {
  const router = buildTestRouter()
  await router.push(`/directories/${directoryId}/files`)
  await router.isReady()
  const wrapper = mount(FilesPage, { global: { plugins: [router] } })
  return { router, wrapper }
}

describe('FilesPage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  beforeEach(() => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(makeDirectoryDetail([]))
  })

  it('fetches the directory detail on mount using the route id', async () => {
    const spy = vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(makeDirectoryDetail([]))

    await mountAtFilesRoute(99)
    await flushPromises()

    expect(spy).toHaveBeenCalledWith(99, undefined)
  })

  it('shows a loading spinner while the API call is in flight', async () => {
    let resolveDetail: ((value: DirectoryDetail) => void) | null = null
    vi.spyOn(api, 'getDirectoryDetail').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDetail = resolve
        }),
    )

    const { wrapper } = await mountAtFilesRoute()

    expect(wrapper.text()).toContain('Loading files')
    expect(wrapper.html()).toContain('animate-spin')

    resolveDetail!(makeDirectoryDetail([]))
    await flushPromises()

    expect(wrapper.text()).not.toContain('Loading files')
  })

  it('renders the table with the four expected columns when files exist', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(
      makeDirectoryDetail([
        makeFile({ id: 1, filename: 'one.epub', format: 'EPUB', status: 'pending', sort_order: 1 }),
        makeFile({ id: 2, filename: 'two.pdf', format: 'PDF', status: 'accepted', sort_order: 2 }),
      ]),
    )

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    const headers = wrapper.findAll('th').map((th) => th.text())
    expect(headers).toEqual(['Filename', 'Format', 'Status', 'Sort order'])

    expect(wrapper.text()).toContain('one.epub')
    expect(wrapper.text()).toContain('two.pdf')
    expect(wrapper.text()).toContain('EPUB')
    expect(wrapper.text()).toContain('PDF')
  })

  it('shows the empty-state message when the API returns zero files', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(makeDirectoryDetail([]))

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('No files match the current filter')
  })

  it('shows an error message when the API call rejects', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockRejectedValue(new Error('500 Server Error'))

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load files')
    expect(wrapper.text()).toContain('500 Server Error')
  })

  it('renders the status filter dropdown with all FILE_STATUSES plus an "All" option', async () => {
    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    const options = wrapper.findAll('option').map((o) => o.element.value)
    expect(options).toContain('')
    expect(options).toContain('pending')
    expect(options).toContain('reading')
    expect(options).toContain('read')
    expect(options).toContain('ai_queued')
    expect(options).toContain('analyze_queued')
    expect(options).toContain('enriching')
    expect(options).toContain('enriched')
    expect(options).toContain('accepted')
    expect(options).toContain('rejected')
    expect(options).toContain('failed')
    expect(options).toContain('missing')
  })

  it('defaults to the "All" filter (no implicit pending-only view) so files of every status load', async () => {
    const spy = vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(makeDirectoryDetail([]))

    await mountAtFilesRoute(42)
    await flushPromises()

    // undefined filter == no ?status query == server returns every status.
    expect(spy).toHaveBeenCalledWith(42, undefined)
  })

  it('renders read and missing files via status chips (a moved file does not vanish)', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(
      makeDirectoryDetail([
        makeFile({ id: 1, filename: 'fresh.epub', status: 'read' }),
        makeFile({ id: 2, filename: 'gone.epub', status: 'missing' }),
      ]),
    )

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('fresh.epub')
    expect(wrapper.text()).toContain('gone.epub')
    const rowText = wrapper.findAll('tbody tr').map((r) => r.text()).join(' ')
    expect(rowText).toContain('read')
    expect(rowText).toContain('missing')
  })

  it('shows per-status counts for the loaded files', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(
      makeDirectoryDetail([
        makeFile({ id: 1, filename: 'a.epub', status: 'read' }),
        makeFile({ id: 2, filename: 'b.epub', status: 'read' }),
        makeFile({ id: 3, filename: 'c.epub', status: 'missing' }),
        makeFile({ id: 4, filename: 'd.epub', status: 'accepted' }),
      ]),
    )

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    expect(wrapper.find('[data-test="status-counts"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="status-count-read"]').text()).toContain('2')
    expect(wrapper.find('[data-test="status-count-missing"]').text()).toContain('1')
    expect(wrapper.find('[data-test="status-count-accepted"]').text()).toContain('1')
    // statuses with zero files are not listed
    expect(wrapper.find('[data-test="status-count-pending"]').exists()).toBe(false)
  })

  it('re-fetches with the selected status filter when the dropdown changes', async () => {
    const spy = vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(makeDirectoryDetail([]))

    const { wrapper } = await mountAtFilesRoute(42)
    await flushPromises()
    spy.mockClear()

    const select = wrapper.find('select')
    await select.setValue('accepted')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith(42, 'accepted')
  })

  it('falls back to the empty string filter (no query param) when "All" is re-selected', async () => {
    const spy = vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(makeDirectoryDetail([]))

    const { wrapper } = await mountAtFilesRoute(42)
    await flushPromises()

    await wrapper.find('select').setValue('accepted')
    await flushPromises()
    spy.mockClear()

    await wrapper.find('select').setValue('')
    await flushPromises()

    expect(spy).toHaveBeenCalledWith(42, undefined)
  })

  it('falls back to the file extension when format is null', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(
      makeDirectoryDetail([makeFile({ id: 1, filename: 'mystery.azw3', extension: 'azw3', format: null })]),
    )

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('azw3')
  })

  it('renders an em-dash placeholder when sort_order is null', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(
      makeDirectoryDetail([makeFile({ id: 1, filename: 'untagged.epub', sort_order: null })]),
    )

    const { wrapper } = await mountAtFilesRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('—')
  })

  it('navigates to the file detail named route when a row is clicked', async () => {
    vi.spyOn(api, 'getDirectoryDetail').mockResolvedValue(
      makeDirectoryDetail([makeFile({ id: 77, filename: 'book.epub' })]),
    )

    const router = buildTestRouter()
    await router.push('/directories/42/files')
    await router.isReady()
    const pushSpy = vi.spyOn(router, 'push')

    const wrapper = mount(FilesPage, { global: { plugins: [router] } })
    await flushPromises()

    const row = wrapper.findAll('tbody tr').at(0)
    expect(row).toBeTruthy()
    await row!.trigger('click')

    expect(pushSpy).toHaveBeenCalledWith({ name: 'file-detail', params: { id: 77 } })
  })

  it('sets the loadError flag when the route id is not a positive integer', async () => {
    const router = buildTestRouter()
    // Register a permissive route for the invalid case so the matcher accepts it.
    router.addRoute({ path: '/directories/:id/files', name: 'files', component: FilesPage })
    await router.push('/directories/abc/files')
    await router.isReady()

    const wrapper = mount(FilesPage, { global: { plugins: [router] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid directory id in URL')
  })
})
