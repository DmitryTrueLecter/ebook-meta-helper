import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import DirectoryTreeNode from '@/components/DirectoryTreeNode.vue'
import * as api from '@/services/api'
import type { DirectoryNode } from '@/types'

function makeNode(overrides: Partial<DirectoryNode> = {}): DirectoryNode {
  return {
    id: 1,
    name: 'root',
    path: '/lib/root',
    depth: 0,
    file_count: 10,
    pending_count: 3,
    enriched_count: 4,
    accepted_count: 2,
    children: [],
    ...overrides,
  }
}

function buildTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/directories' },
      { path: '/directories', name: 'directories', component: { template: '<div />' } },
      { path: '/directories/:id/files', name: 'files', component: { template: '<div />' } },
      { path: '/scan', name: 'scan', component: { template: '<div />' } },
    ],
  })
}

describe('DirectoryTreeNode', () => {
  let testRouter: Router

  beforeEach(() => {
    testRouter = buildTestRouter()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the directory name and all four count badges', () => {
    const node = makeNode({ name: 'fiction', file_count: 42, pending_count: 5, enriched_count: 30, accepted_count: 7 })

    const wrapper = mount(DirectoryTreeNode, {
      props: { node },
      global: { plugins: [testRouter] },
    })

    expect(wrapper.text()).toContain('fiction')
    expect(wrapper.text()).toContain('42 files')
    expect(wrapper.text()).toContain('5 pending')
    expect(wrapper.text()).toContain('30 enriched')
    expect(wrapper.text()).toContain('7 accepted')
  })

  it('navigates to the files route for this directory when the name is clicked', async () => {
    const pushSpy = vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)
    const node = makeNode({ id: 99 })

    const wrapper = mount(DirectoryTreeNode, {
      props: { node },
      global: { plugins: [testRouter] },
    })

    const nameButton = wrapper.findAll('button').find((b) => b.text() === 'root')
    expect(nameButton).toBeTruthy()
    await nameButton!.trigger('click')

    expect(pushSpy).toHaveBeenCalledWith({ name: 'files', params: { id: 99 } })
  })

  it('calls triggerDirectoryScan and navigates to /scan when Scan is clicked', async () => {
    const triggerSpy = vi
      .spyOn(api, 'triggerDirectoryScan')
      .mockResolvedValue({ id: 1, status: 'queued', files_discovered: 0, files_processed: 0, current_filename: null })
    const pushSpy = vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)
    const node = makeNode({ id: 7 })

    const wrapper = mount(DirectoryTreeNode, {
      props: { node },
      global: { plugins: [testRouter] },
    })

    const scanButton = wrapper.findAll('button').find((b) => b.text().includes('Scan'))
    expect(scanButton).toBeTruthy()
    await scanButton!.trigger('click')
    await flushPromises()

    expect(triggerSpy).toHaveBeenCalledWith(7)
    expect(pushSpy).toHaveBeenCalledWith({ name: 'scan' })
  })

  it('disables the Scan button and shows a spinner while a scan is in flight', async () => {
    let resolveScan: (() => void) | null = null
    vi.spyOn(api, 'triggerDirectoryScan').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveScan = () => resolve({ id: 1, status: 'queued', files_discovered: 0, files_processed: 0, current_filename: null })
        }),
    )
    vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)

    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode() },
      global: { plugins: [testRouter] },
    })

    const scanButton = wrapper.findAll('button').find((b) => b.text().includes('Scan'))!
    await scanButton.trigger('click')

    expect(scanButton.attributes('disabled')).toBeDefined()
    expect(scanButton.html()).toContain('animate-spin')

    resolveScan!()
    await flushPromises()

    expect(scanButton.attributes('disabled')).toBeUndefined()
  })

  it('surfaces a scan failure as visible error text and re-enables the button', async () => {
    vi.spyOn(api, 'triggerDirectoryScan').mockRejectedValue(new Error('scan worker offline'))
    vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)

    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode() },
      global: { plugins: [testRouter] },
    })

    const scanButton = wrapper.findAll('button').find((b) => b.text().includes('Scan'))!
    await scanButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('scan worker offline')
    expect(scanButton.attributes('disabled')).toBeUndefined()
  })

  it('renders children when expanded and hides them when collapsed', async () => {
    const child = makeNode({ id: 2, name: 'sub' })
    const root = makeNode({ id: 1, name: 'root', children: [child] })

    const wrapper = mount(DirectoryTreeNode, {
      props: { node: root },
      global: { plugins: [testRouter] },
    })

    expect(wrapper.text()).toContain('sub')

    const collapseButton = wrapper.find('[aria-label="Collapse"]')
    expect(collapseButton.exists()).toBe(true)
    await collapseButton.trigger('click')

    expect(wrapper.text()).not.toContain('sub')
  })

  it('does not render a collapse/expand chevron when the directory has no children', () => {
    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode({ children: [] }) },
      global: { plugins: [testRouter] },
    })

    expect(wrapper.find('[aria-label="Collapse"]').exists()).toBe(false)
    expect(wrapper.find('[aria-label="Expand"]').exists()).toBe(false)
  })
})
