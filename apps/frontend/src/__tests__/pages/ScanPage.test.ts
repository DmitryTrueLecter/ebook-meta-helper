import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import ScanPage from '@/pages/ScanPage.vue'
import * as api from '@/services/api'
import type { DirectoryNode, ScanJobStatus } from '@/types'

function makeNode(overrides: Partial<DirectoryNode> = {}): DirectoryNode {
  return {
    id: 1,
    name: 'root',
    path: '/lib',
    depth: 0,
    file_count: 0,
    pending_count: 0,
    enriched_count: 0,
    accepted_count: 0,
    children: [],
    ...overrides,
  }
}

function makeJob(overrides: Partial<ScanJobStatus> = {}): ScanJobStatus {
  return {
    id: 1,
    status: 'running',
    files_discovered: 100,
    files_processed: 25,
    current_filename: 'currently.epub',
    ...overrides,
  }
}

function buildTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/scan', name: 'scan', component: ScanPage },
      { path: '/directories', name: 'directories', component: { template: '<div />' } },
    ],
  })
}

async function mountAtScanRoute(): Promise<VueWrapper> {
  const router = buildTestRouter()
  await router.push('/scan')
  await router.isReady()
  return mount(ScanPage, { global: { plugins: [router] } })
}

describe('ScanPage', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('calls listDirectories and getScanStatus on mount', async () => {
    const dirsSpy = vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    await mountAtScanRoute()
    await flushPromises()

    expect(dirsSpy).toHaveBeenCalledOnce()
    expect(statusSpy).toHaveBeenCalledOnce()
  })

  it('shows a loading state while the mount fetches are in flight', async () => {
    vi.spyOn(api, 'listDirectories').mockImplementation(() => new Promise(() => {}))
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    const wrapper = await mountAtScanRoute()

    expect(wrapper.text()).toContain('Loading scan state')
    expect(wrapper.html()).toContain('animate-spin')
  })

  it('surfaces a mount-time error and does not render the launcher', async () => {
    vi.spyOn(api, 'listDirectories').mockRejectedValue(new Error('500 Server Error'))
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load scan state')
    expect(wrapper.text()).toContain('500 Server Error')
    expect(wrapper.text()).not.toContain('Start Scan')
  })

  it('renders the launcher with directory options from a flattened tree', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({
        id: 1,
        name: 'fiction',
        children: [makeNode({ id: 2, name: 'sci-fi', children: [] })],
      }),
      makeNode({ id: 3, name: 'non-fiction', children: [] }),
    ])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    const select = wrapper.find('select#scan-directory')
    expect(select.exists()).toBe(true)

    const labels = wrapper.findAll('option').map((o) => o.text())
    expect(labels).toContain('fiction')
    expect(labels).toContain('fiction / sci-fi')
    expect(labels).toContain('non-fiction')
  })

  it('shows a hint and no options when no directories exist', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('No directories discovered yet')
  })

  it('keeps the Start Scan button disabled until a directory is selected', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 7, name: 'one', children: [] }),
    ])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    const startButton = wrapper.findAll('button').find((b) => b.text().includes('Start Scan'))
    expect(startButton).toBeTruthy()
    expect(startButton!.attributes('disabled')).toBeDefined()

    await wrapper.find('select#scan-directory').setValue('7')
    expect(startButton!.attributes('disabled')).toBeUndefined()
  })

  it('calls triggerDirectoryScan with the selected id when Start Scan is clicked', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 7, name: 'one', children: [] }),
    ])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)
    const triggerSpy = vi
      .spyOn(api, 'triggerDirectoryScan')
      .mockResolvedValue(makeJob({ status: 'pending', files_discovered: 0, files_processed: 0 }))

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    await wrapper.find('select#scan-directory').setValue('7')

    const startButton = wrapper.findAll('button').find((b) => b.text().includes('Start Scan'))!
    await startButton.trigger('click')
    await flushPromises()

    expect(triggerSpy).toHaveBeenCalledWith(7)
  })

  it('surfaces a start-scan failure as visible error text and re-enables the button', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 7, name: 'one', children: [] }),
    ])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)
    vi.spyOn(api, 'triggerDirectoryScan').mockRejectedValue(new Error('scan worker offline'))

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    await wrapper.find('select#scan-directory').setValue('7')

    const startButton = wrapper.findAll('button').find((b) => b.text().includes('Start Scan'))!
    await startButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('scan worker offline')
    expect(startButton.attributes('disabled')).toBeUndefined()
  })

  it('renders the progress panel when a scan is already active on mount', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(
      makeJob({ status: 'running', files_discovered: 200, files_processed: 50, current_filename: 'book.epub' }),
    )

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.text()).toContain('50 / 200')
    expect(wrapper.text()).toContain('book.epub')
    expect(wrapper.find('[data-test="scan-status-running"]').exists()).toBe(true)
  })

  it('shows the progress bar at the correct percentage', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(
      makeJob({ status: 'running', files_discovered: 200, files_processed: 50 }),
    )

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    const bar = wrapper.find('[role="progressbar"]')
    expect(bar.exists()).toBe(true)
    expect(bar.attributes('aria-valuenow')).toBe('25')
  })

  it('shows 0% when files_discovered is zero (no division by zero)', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(
      makeJob({ status: 'pending', files_discovered: 0, files_processed: 0 }),
    )

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    const bar = wrapper.find('[role="progressbar"]')
    expect(bar.attributes('aria-valuenow')).toBe('0')
  })

  it('shows the done summary when status is done', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(
      makeJob({ status: 'done', files_discovered: 10, files_processed: 10 }),
    )

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    expect(wrapper.find('[data-test="scan-done-summary"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Scan complete')
  })

  it('shows the failed summary when status is failed', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    vi.spyOn(api, 'getScanStatus').mockResolvedValue(
      makeJob({ status: 'failed', files_discovered: 10, files_processed: 3 }),
    )

    const wrapper = await mountAtScanRoute()
    await flushPromises()

    expect(wrapper.find('[data-test="scan-failed-summary"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Scan failed')
  })

  it('polls every 2 seconds while a scan is running', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'running' }))
    statusSpy.mockResolvedValue(makeJob({ status: 'running' }))

    await mountAtScanRoute()
    await flushPromises()

    expect(statusSpy).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(3)
  })

  it('stops polling when the scan transitions to done', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'running' }))
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'done', files_processed: 100, files_discovered: 100 }))

    await mountAtScanRoute()
    await flushPromises()
    expect(statusSpy).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(2)

    // After done, further timer advances must not trigger more polls.
    await vi.advanceTimersByTimeAsync(4000)
    expect(statusSpy).toHaveBeenCalledTimes(2)
  })

  it('stops polling when the scan transitions to failed', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'running' }))
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'failed' }))

    await mountAtScanRoute()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(4000)
    expect(statusSpy).toHaveBeenCalledTimes(2)
  })

  it('does not start polling when the initial scan status is null', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)

    await mountAtScanRoute()
    await flushPromises()
    expect(statusSpy).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(6000)
    expect(statusSpy).toHaveBeenCalledTimes(1)
  })

  it('does not start polling when the initial scan status is already done', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi
      .spyOn(api, 'getScanStatus')
      .mockResolvedValue(makeJob({ status: 'done' }))

    await mountAtScanRoute()
    await flushPromises()
    expect(statusSpy).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(6000)
    expect(statusSpy).toHaveBeenCalledTimes(1)
  })

  it('starts polling after a successful Start Scan when the backend returns running', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 7, name: 'one', children: [] }),
    ])
    const statusSpy = vi.spyOn(api, 'getScanStatus').mockResolvedValue(null)
    vi.spyOn(api, 'triggerDirectoryScan').mockResolvedValue(
      makeJob({ status: 'running', files_discovered: 0, files_processed: 0 }),
    )

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    expect(statusSpy).toHaveBeenCalledTimes(1)

    await wrapper.find('select#scan-directory').setValue('7')
    const startButton = wrapper.findAll('button').find((b) => b.text().includes('Start Scan'))!
    await startButton.trigger('click')
    await flushPromises()

    statusSpy.mockResolvedValue(makeJob({ status: 'running' }))
    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(2)
  })

  it('clears the polling interval on unmount', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi
      .spyOn(api, 'getScanStatus')
      .mockResolvedValue(makeJob({ status: 'running' }))

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    expect(statusSpy).toHaveBeenCalledTimes(1)

    wrapper.unmount()

    await vi.advanceTimersByTimeAsync(6000)
    expect(statusSpy).toHaveBeenCalledTimes(1)
  })

  it('stops polling when a poll request rejects (does not keep hammering a broken endpoint)', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'running' }))
    statusSpy.mockRejectedValueOnce(new Error('network down'))

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()

    expect(statusSpy).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('network down')

    await vi.advanceTimersByTimeAsync(6000)
    expect(statusSpy).toHaveBeenCalledTimes(2)
  })

  it('keeps the launcher and last-known progress visible when a poll rejects (does not nuke the page)', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 7, name: 'one', children: [] }),
    ])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    statusSpy.mockResolvedValueOnce(
      makeJob({ status: 'running', files_discovered: 200, files_processed: 50 }),
    )
    statusSpy.mockRejectedValueOnce(new Error('network down'))

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()

    // Inline alert appears.
    expect(wrapper.find('[data-test="scan-poll-error"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('network down')
    // But the mount-time failure banner does NOT — different ref, different placement.
    expect(wrapper.text()).not.toContain('Failed to load scan state')
    // Launcher is still rendered (Start Scan button visible).
    expect(wrapper.text()).toContain('Start Scan')
    // Last known progress is still rendered.
    expect(wrapper.text()).toContain('50 / 200')
    expect(wrapper.find('[role="progressbar"]').exists()).toBe(true)
  })

  it('does not schedule a second poll while the first is still in flight (no re-entrancy)', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    // First call (mount) — synchronous resolve.
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'running' }))
    // Second call (first poll) — never resolves; simulates a slow network.
    let resolveSecond: (value: ScanJobStatus) => void = () => {}
    statusSpy.mockReturnValueOnce(
      new Promise<ScanJobStatus>((resolve) => {
        resolveSecond = resolve
      }),
    )
    statusSpy.mockResolvedValue(makeJob({ status: 'running' }))

    await mountAtScanRoute()
    await flushPromises()
    expect(statusSpy).toHaveBeenCalledTimes(1)

    // Advance to fire the first scheduled poll.
    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(2)

    // First poll hasn't resolved yet — advancing further must NOT spawn another call.
    await vi.advanceTimersByTimeAsync(4000)
    expect(statusSpy).toHaveBeenCalledTimes(2)

    // Resolve the slow poll → next poll only schedules now.
    resolveSecond(makeJob({ status: 'running' }))
    await flushPromises()

    await vi.advanceTimersByTimeAsync(2000)
    expect(statusSpy).toHaveBeenCalledTimes(3)
  })

  it('clears the inline poll-error when polling resumes successfully on Start Scan', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 7, name: 'one', children: [] }),
    ])
    const statusSpy = vi.spyOn(api, 'getScanStatus')
    statusSpy.mockResolvedValueOnce(makeJob({ status: 'running' }))
    statusSpy.mockRejectedValueOnce(new Error('network down'))

    const wrapper = await mountAtScanRoute()
    await flushPromises()
    await vi.advanceTimersByTimeAsync(2000)
    await flushPromises()
    expect(wrapper.find('[data-test="scan-poll-error"]').exists()).toBe(true)

    // User retries via Start Scan — successful trigger should clear the inline alert.
    vi.spyOn(api, 'triggerDirectoryScan').mockResolvedValue(
      makeJob({ status: 'running', files_discovered: 0, files_processed: 0 }),
    )
    await wrapper.find('select#scan-directory').setValue('7')
    const startButton = wrapper.findAll('button').find((b) => b.text().includes('Start Scan'))!
    await startButton.trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-test="scan-poll-error"]').exists()).toBe(false)
  })
})
