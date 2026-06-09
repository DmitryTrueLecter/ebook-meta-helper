import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AICallDetailPanel from '@/components/AICallDetailPanel.vue'
import type { AICallDetail } from '@/types'

function detail(overrides: Partial<AICallDetail> = {}): AICallDetail {
  return {
    id: 2,
    file_id: 7,
    enrichment_run_id: 3,
    sequence: 2,
    tier: 'expensive',
    is_canonical: true,
    model: 'gpt-4o',
    confidence: 0.92,
    prompt_tokens: 1500,
    completion_tokens: 400,
    cost_usd: 0.012,
    duration_ms: 1800,
    created_at: '2026-06-08T10:01:00Z',
    system_prompt: 'You are a metadata extractor.',
    user_prompt: 'Extract metadata from: book.epub',
    raw_response: '{"title": "Dune"}',
    response_format_ref: 'metadata_v1',
    effort: 'high',
    parse_errors: null,
    origin: 'escalation',
    config_version_id: 5,
    ...overrides,
  }
}

describe('AICallDetailPanel', () => {
  it('renders system prompt, user prompt, and raw response', () => {
    const wrapper = mount(AICallDetailPanel, { props: { call: detail() } })

    const text = wrapper.text()
    expect(text).toContain('You are a metadata extractor.')
    expect(text).toContain('Extract metadata from: book.epub')
    expect(text).toContain('{"title": "Dune"}')
  })

  it('exposes prompts and response in their own collapsible blocks', () => {
    const wrapper = mount(AICallDetailPanel, { props: { call: detail() } })

    expect(wrapper.find('[data-testid="system-prompt-block"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="user-prompt-block"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="raw-response-block"]').exists()).toBe(true)
  })

  it('hides the parse-errors block and shows a clear note when there are none', () => {
    const wrapper = mount(AICallDetailPanel, { props: { call: detail({ parse_errors: null }) } })

    expect(wrapper.find('[data-testid="parse-errors-block"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('No parse errors recorded')
  })

  it('renders a string parse error verbatim', () => {
    const wrapper = mount(AICallDetailPanel, {
      props: { call: detail({ parse_errors: 'unexpected token at line 2' }) },
    })

    expect(wrapper.find('[data-testid="parse-errors-block"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('unexpected token at line 2')
  })

  it('pretty-prints a structured parse error payload', () => {
    const wrapper = mount(AICallDetailPanel, {
      props: { call: detail({ parse_errors: { field: 'authors', issue: 'missing' } }) },
    })

    const text = wrapper.text()
    expect(text).toContain('"field"')
    expect(text).toContain('authors')
    expect(text).toContain('missing')
  })

  it('treats an empty-string parse error as no error', () => {
    const wrapper = mount(AICallDetailPanel, { props: { call: detail({ parse_errors: '' }) } })

    expect(wrapper.find('[data-testid="parse-errors-block"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('No parse errors recorded')
  })
})
