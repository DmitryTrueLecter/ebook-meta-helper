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
    status: 'active',
    file_count: 10,
    pending_count: 3,
    enriched_count: 4,
    accepted_count: 2,
    missing_count: 0,
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

  it('exposes Discover as the only per-directory action (no analyze/scan control)', () => {
    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode() },
      global: { plugins: [testRouter] },
    })

    const actionButtons = wrapper.findAll('button').map((b) => b.text())
    expect(actionButtons.some((t) => t.includes('Discover'))).toBe(true)
    expect(actionButtons.some((t) => /analyze/i.test(t))).toBe(false)
    expect(actionButtons.some((t) => /scan/i.test(t))).toBe(false)
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

  it('calls discoverDirectory and navigates to /scan when Discover is clicked', async () => {
    const discoverSpy = vi
      .spyOn(api, 'discoverDirectory')
      .mockResolvedValue({ id: 1, status: 'queued', files_discovered: 0, files_processed: 0, current_filename: null })
    const pushSpy = vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)
    const node = makeNode({ id: 7 })

    const wrapper = mount(DirectoryTreeNode, {
      props: { node },
      global: { plugins: [testRouter] },
    })

    const discoverButton = wrapper.findAll('button').find((b) => b.text().includes('Discover'))
    expect(discoverButton).toBeTruthy()
    await discoverButton!.trigger('click')
    await flushPromises()

    expect(discoverSpy).toHaveBeenCalledWith(7)
    expect(pushSpy).toHaveBeenCalledWith({ name: 'scan' })
  })

  it('disables the Discover button and shows a spinner while discovery is in flight', async () => {
    let resolveDiscover: (() => void) | null = null
    vi.spyOn(api, 'discoverDirectory').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveDiscover = () => resolve({ id: 1, status: 'queued', files_discovered: 0, files_processed: 0, current_filename: null })
        }),
    )
    vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)

    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode() },
      global: { plugins: [testRouter] },
    })

    const discoverButton = wrapper.findAll('button').find((b) => b.text().includes('Discover'))!
    await discoverButton.trigger('click')

    expect(discoverButton.attributes('disabled')).toBeDefined()
    expect(discoverButton.html()).toContain('animate-spin')

    resolveDiscover!()
    await flushPromises()

    expect(discoverButton.attributes('disabled')).toBeUndefined()
  })

  it('surfaces a discover failure as visible error text and re-enables the button', async () => {
    vi.spyOn(api, 'discoverDirectory').mockRejectedValue(new Error('discover worker offline'))
    vi.spyOn(testRouter, 'push').mockResolvedValue(undefined)

    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode() },
      global: { plugins: [testRouter] },
    })

    const discoverButton = wrapper.findAll('button').find((b) => b.text().includes('Discover'))!
    await discoverButton.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('discover worker offline')
    expect(discoverButton.attributes('disabled')).toBeUndefined()
  })

  it('renders a missing badge and missing_count when the directory is archived', () => {
    const wrapper = mount(DirectoryTreeNode, {
      props: { node: makeNode({ status: 'missing', missing_count: 4 }) },
      global: { plugins: [testRouter] },
    })

    expect(wrapper.find('[data-test="directory-missing-badge"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="directory-missing-count"]').text()).toContain('4 missing')
  })

  it('always hides missing child directories', async () => {
    const liveChild = makeNode({ id: 2, name: 'live-sub', status: 'active' })
    const goneChild = makeNode({ id: 3, name: 'gone-sub', status: 'missing' })
    const root = makeNode({ id: 1, name: 'root', children: [liveChild, goneChild] })

    const wrapper = mount(DirectoryTreeNode, {
      props: { node: root },
      global: { plugins: [testRouter] },
    })
    expect(wrapper.text()).toContain('live-sub')
    expect(wrapper.text()).not.toContain('gone-sub')
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
