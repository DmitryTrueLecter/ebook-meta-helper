import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AICallList from '@/components/AICallList.vue'
import type { AICallSummary } from '@/types'

function call(overrides: Partial<AICallSummary> = {}): AICallSummary {
  return {
    id: 1,
    file_id: 7,
    enrichment_run_id: 3,
    sequence: 1,
    tier: 'cheap',
    is_canonical: false,
    model: 'gpt-4o-mini',
    confidence: 0.42,
    prompt_tokens: 1200,
    completion_tokens: 300,
    cost_usd: 0.0021,
    duration_ms: 850,
    created_at: '2026-06-08T10:00:00Z',
    ...overrides,
  }
}

// A cheap call that escalated to an expensive one, with the expensive call as canonical.
function escalationChain(): AICallSummary[] {
  return [
    call({ id: 1, sequence: 1, tier: 'cheap', model: 'gpt-4o-mini', confidence: 0.4 }),
    call({
      id: 2,
      sequence: 2,
      tier: 'expensive',
      model: 'gpt-4o',
      confidence: 0.92,
      is_canonical: true,
    }),
  ]
}

describe('AICallList', () => {
  it('renders one row per call in the escalation chain', () => {
    const wrapper = mount(AICallList, { props: { calls: escalationChain() } })

    expect(wrapper.findAll('li')).toHaveLength(2)
  })

  it('shows both tiers of a 2-call escalation chain', () => {
    const wrapper = mount(AICallList, { props: { calls: escalationChain() } })

    const text = wrapper.text()
    expect(text).toContain('cheap')
    expect(text).toContain('expensive')
  })

  it('marks the canonical call and only that call', () => {
    const wrapper = mount(AICallList, { props: { calls: escalationChain() } })

    const markers = wrapper.findAll('[data-testid="canonical-marker"]')
    expect(markers).toHaveLength(1)

    // The marker lives on the expensive call (id 2), not the cheap one (id 1).
    const canonicalRow = wrapper.get('[data-testid="ai-call-2"]')
    const cheapRow = wrapper.get('[data-testid="ai-call-1"]')
    expect(canonicalRow.find('[data-testid="canonical-marker"]').exists()).toBe(true)
    expect(cheapRow.find('[data-testid="canonical-marker"]').exists()).toBe(false)
  })

  it('renders model, confidence, tokens, cost, and duration per call', () => {
    const wrapper = mount(AICallList, { props: { calls: [call()] } })

    const text = wrapper.text()
    expect(text).toContain('gpt-4o-mini')
    expect(text).toContain('42%')
    expect(text).toContain('1200 / 300')
    expect(text).toContain('$0.0021')
    expect(text).toContain('850 ms')
  })

  it('formats multi-second durations with two decimals', () => {
    const wrapper = mount(AICallList, { props: { calls: [call({ duration_ms: 2500 })] } })

    expect(wrapper.text()).toContain('2.50 s')
  })

  it('renders an em dash for null confidence, tokens, and cost', () => {
    const wrapper = mount(AICallList, {
      props: {
        calls: [
          call({ confidence: null, prompt_tokens: null, completion_tokens: null, cost_usd: null }),
        ],
      },
    })

    const text = wrapper.text()
    expect(text).toContain('—')
  })

  it('emits select with the call id on click', async () => {
    const wrapper = mount(AICallList, { props: { calls: escalationChain() } })

    await wrapper.get('[data-testid="ai-call-2"]').trigger('click')

    expect(wrapper.emitted('select')?.[0]).toEqual([2])
  })

  it('highlights the selected call', () => {
    const wrapper = mount(AICallList, { props: { calls: escalationChain(), selectedId: 2 } })

    expect(wrapper.get('[data-testid="ai-call-2"]').classes()).toContain('border-primary')
    expect(wrapper.get('[data-testid="ai-call-1"]').classes()).not.toContain('border-primary')
  })

  it('renders nothing inside the list when there are no calls', () => {
    const wrapper = mount(AICallList, { props: { calls: [] } })

    expect(wrapper.findAll('li')).toHaveLength(0)
  })
})
