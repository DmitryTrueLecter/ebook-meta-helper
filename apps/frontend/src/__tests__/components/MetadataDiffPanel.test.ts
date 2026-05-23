import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import MetadataDiffPanel from '@/components/MetadataDiffPanel.vue'
import type { DiffRow } from '@/composables/useMetadataDiff'

function row(overrides: Partial<DiffRow> = {}): DiffRow {
  return {
    label: 'Title',
    key: 'title',
    fileValue: 'A',
    aiValue: 'B',
    highlight: 'changed',
    ...overrides,
  }
}

describe('MetadataDiffPanel', () => {
  it('renders the panel title', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: { title: 'AI suggestion', side: 'ai', rows: [row()] },
    })

    expect(wrapper.text()).toContain('AI suggestion')
  })

  it('renders the empty message when isEmpty is true', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'Original',
        side: 'file',
        rows: [row()],
        isEmpty: true,
        emptyMessage: 'No metadata read from file yet.',
      },
    })

    expect(wrapper.text()).toContain('No metadata read from file yet.')
    // Empty state hides the rows.
    expect(wrapper.text()).not.toContain('A')
  })

  it('on the file side, renders fileValue and applies no highlight class', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'Original',
        side: 'file',
        rows: [row({ highlight: 'changed', fileValue: 'File A', aiValue: 'AI B' })],
      },
    })

    expect(wrapper.text()).toContain('File A')
    expect(wrapper.text()).not.toContain('AI B')
    expect(wrapper.html()).not.toContain('bg-yellow-100')
    expect(wrapper.html()).not.toContain('bg-green-100')
  })

  it('on the AI side, renders aiValue and applies the yellow highlight for "changed"', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'AI',
        side: 'ai',
        rows: [row({ highlight: 'changed', fileValue: 'File A', aiValue: 'AI B' })],
      },
    })

    expect(wrapper.text()).toContain('AI B')
    expect(wrapper.text()).not.toContain('File A')
    expect(wrapper.html()).toContain('bg-yellow-100')
  })

  it('on the AI side, applies the green highlight for "new"', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'AI',
        side: 'ai',
        rows: [row({ highlight: 'new', fileValue: '', aiValue: 'Brand New' })],
      },
    })

    expect(wrapper.html()).toContain('bg-green-100')
    expect(wrapper.html()).not.toContain('bg-yellow-100')
  })

  it('on the AI side with highlight "none", applies neither highlight class', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'AI',
        side: 'ai',
        rows: [row({ highlight: 'none', fileValue: 'X', aiValue: 'X' })],
      },
    })

    expect(wrapper.html()).not.toContain('bg-yellow-100')
    expect(wrapper.html()).not.toContain('bg-green-100')
  })

  it('renders an em-dash placeholder when the value is empty', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'AI',
        side: 'ai',
        rows: [row({ highlight: 'none', fileValue: '', aiValue: '' })],
      },
    })

    expect(wrapper.text()).toContain('—')
  })

  it('renders every row in order', () => {
    const wrapper = mount(MetadataDiffPanel, {
      props: {
        title: 'AI',
        side: 'ai',
        rows: [
          row({ key: 'title', label: 'Title', aiValue: 'T' }),
          row({ key: 'authors', label: 'Authors', aiValue: 'A' }),
          row({ key: 'tags', label: 'Tags', aiValue: 'G' }),
        ],
      },
    })

    expect(wrapper.text()).toContain('Title')
    expect(wrapper.text()).toContain('Authors')
    expect(wrapper.text()).toContain('Tags')
  })
})
