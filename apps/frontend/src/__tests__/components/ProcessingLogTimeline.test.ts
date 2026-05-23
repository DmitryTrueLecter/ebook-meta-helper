import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ProcessingLogTimeline from '@/components/ProcessingLogTimeline.vue'
import type { ProcessingLogEntry } from '@/types'

function entry(overrides: Partial<ProcessingLogEntry> = {}): ProcessingLogEntry {
  return {
    step: 'read_metadata',
    level: 'info',
    message: 'parsed cover image',
    duration_ms: 12,
    created_at: '2026-05-23T10:00:00Z',
    ...overrides,
  }
}

describe('ProcessingLogTimeline', () => {
  it('renders one li per entry', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: {
        entries: [
          entry({ step: 'a' }),
          entry({ step: 'b' }),
          entry({ step: 'c' }),
        ],
      },
    })

    expect(wrapper.findAll('li')).toHaveLength(3)
  })

  it('shows step name, message, and a parsed timestamp', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ step: 'parse_epub', message: 'parsed cover image' })] },
    })

    const text = wrapper.text()
    expect(text).toContain('parse_epub')
    expect(text).toContain('parsed cover image')
    // toLocaleString output varies by environment; assert the year at minimum.
    expect(text).toMatch(/2026/)
  })

  it('renders info entries with a check glyph', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ level: 'info' })] },
    })

    expect(wrapper.text()).toContain('✓')
  })

  it('renders warning entries with a warn glyph', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ level: 'warning' })] },
    })

    expect(wrapper.text()).toContain('⚠')
  })

  it('renders error entries with a cross glyph', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ level: 'error' })] },
    })

    expect(wrapper.text()).toContain('✗')
  })

  it('falls back to a neutral dot for unknown levels', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ level: 'mystery' })] },
    })

    expect(wrapper.text()).toContain('•')
  })

  it('formats sub-second durations as "<n> ms"', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ duration_ms: 250 })] },
    })

    expect(wrapper.text()).toContain('250 ms')
  })

  it('formats multi-second durations with two decimals', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ duration_ms: 2500 })] },
    })

    expect(wrapper.text()).toContain('2.50 s')
  })

  it('omits the duration column when duration_ms is null', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ duration_ms: null })] },
    })

    const text = wrapper.text()
    expect(text).not.toMatch(/\bms\b/)
    expect(text).not.toMatch(/\bs$/)
  })

  it('falls back to the raw timestamp string when it cannot be parsed', () => {
    const wrapper = mount(ProcessingLogTimeline, {
      props: { entries: [entry({ created_at: 'not-a-date' })] },
    })

    expect(wrapper.text()).toContain('not-a-date')
  })

  it('renders nothing inside the list when entries is empty', () => {
    const wrapper = mount(ProcessingLogTimeline, { props: { entries: [] } })

    expect(wrapper.findAll('li')).toHaveLength(0)
  })
})
