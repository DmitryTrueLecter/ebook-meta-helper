import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

import App from '@/App.vue'

function buildTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/directories' },
      { path: '/directories', name: 'directories', component: { template: '<div data-test="directories" />' } },
      { path: '/scan', name: 'scan', component: { template: '<div data-test="scan" />' } },
    ],
  })
}

describe('App.vue top navigation', () => {
  it('renders the app name', async () => {
    const router = buildTestRouter()
    await router.push('/directories')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router] } })

    expect(wrapper.text()).toContain('Ebook Meta Helper')
  })

  it('renders a Directories link pointing to the directories named route', async () => {
    const router = buildTestRouter()
    await router.push('/directories')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router] } })

    const directoriesLink = wrapper
      .findAll('a')
      .find((a) => a.text() === 'Directories')
    expect(directoriesLink).toBeTruthy()
    expect(directoriesLink!.attributes('href')).toBe('/directories')
  })

  it('renders a Scan link pointing to the scan named route', async () => {
    const router = buildTestRouter()
    await router.push('/directories')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router] } })

    const scanLink = wrapper.findAll('a').find((a) => a.text() === 'Scan')
    expect(scanLink).toBeTruthy()
    expect(scanLink!.attributes('href')).toBe('/scan')
  })

  it('renders the active route view inside the main slot', async () => {
    const router = buildTestRouter()
    await router.push('/directories')
    await router.isReady()

    const wrapper = mount(App, { global: { plugins: [router] } })

    expect(wrapper.find('[data-test="directories"]').exists()).toBe(true)
  })
})
