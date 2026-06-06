import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'

import DirectoriesPage from '@/pages/DirectoriesPage.vue'
import * as api from '@/services/api'
import type { DirectoryNode } from '@/types'

function makeNode(overrides: Partial<DirectoryNode> = {}): DirectoryNode {
  return {
    id: 1,
    name: 'root',
    path: '/lib',
    depth: 0,
    status: 'active',
    file_count: 0,
    pending_count: 0,
    enriched_count: 0,
    accepted_count: 0,
    missing_count: 0,
    children: [],
    ...overrides,
  }
}

function buildTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/directories', name: 'directories', component: { template: '<div />' } },
      { path: '/directories/:id/files', name: 'files', component: { template: '<div />' } },
      { path: '/scan', name: 'scan', component: { template: '<div />' } },
    ],
  })
}

describe('DirectoriesPage', () => {
  let testRouter: Router

  beforeEach(async () => {
    testRouter = buildTestRouter()
    await testRouter.push('/directories')
    await testRouter.isReady()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('calls listDirectories on mount', async () => {
    const spy = vi.spyOn(api, 'listDirectories').mockResolvedValue([])

    mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(spy).toHaveBeenCalledOnce()
  })

  it('shows a loading spinner while the API call is in flight', async () => {
    let resolveListing: ((value: DirectoryNode[]) => void) | null = null
    vi.spyOn(api, 'listDirectories').mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveListing = resolve
        }),
    )

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })

    expect(wrapper.text()).toContain('Loading directories')
    expect(wrapper.html()).toContain('animate-spin')

    resolveListing!([])
    await flushPromises()

    expect(wrapper.text()).not.toContain('Loading directories')
  })

  it('renders the tree when the API returns directories', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({ id: 1, name: 'fiction', file_count: 12 }),
      makeNode({ id: 2, name: 'non-fiction', file_count: 5 }),
    ])

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).toContain('fiction')
    expect(wrapper.text()).toContain('non-fiction')
    expect(wrapper.text()).toContain('12 files')
  })

  it('renders nested children recursively', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({
        id: 1,
        name: 'fiction',
        children: [makeNode({ id: 2, name: 'sci-fi' })],
      }),
    ])

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).toContain('fiction')
    expect(wrapper.text()).toContain('sci-fi')
  })

  it('hides missing child directories until the "show missing" toggle is checked', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([
      makeNode({
        id: 1,
        name: 'fiction',
        children: [makeNode({ id: 2, name: 'archived-sub', status: 'missing' })],
      }),
    ])

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).not.toContain('archived-sub')

    await wrapper.find('input[type="checkbox"]').setValue(true)

    expect(wrapper.text()).toContain('archived-sub')
  })

  it('shows an empty state when the API returns no directories', async () => {
    vi.spyOn(api, 'listDirectories').mockResolvedValue([])

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).toContain('No directories yet')
  })

  it('shows an error message when the API call rejects', async () => {
    vi.spyOn(api, 'listDirectories').mockRejectedValue(new Error('500 Internal Server Error'))

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load directories')
    expect(wrapper.text()).toContain('500 Internal Server Error')
  })

  it('shows an error when the backend returns an empty (204) response — no silent empty-state', async () => {
    vi.spyOn(api, 'listDirectories').mockRejectedValue(
      new Error('Directories listing returned an empty response'),
    )

    const wrapper = mount(DirectoriesPage, { global: { plugins: [testRouter] } })
    await flushPromises()

    expect(wrapper.text()).toContain('Failed to load directories')
    expect(wrapper.text()).not.toContain('No directories yet')
  })
})
