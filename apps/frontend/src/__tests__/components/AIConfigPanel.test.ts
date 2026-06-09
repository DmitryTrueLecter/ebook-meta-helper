import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AIConfigPanel from '@/components/AIConfigPanel.vue'
import type { AIConfigVersionView } from '@/types'

function config(overrides: Partial<AIConfigVersionView> = {}): AIConfigVersionView {
  return {
    id: 5,
    version: 3,
    label: 'tuned-prompt',
    system_prompt: 'You are a metadata extractor.',
    cheap_model: 'gpt-4o-mini',
    expensive_model: 'gpt-4o',
    effort: 'high',
    escalation_threshold: 0.7,
    provider: 'openai',
    response_format_ref: 'metadata_v1',
    is_active: true,
    created_at: '2026-06-08T09:00:00Z',
    created_by: 'dmitry',
    ...overrides,
  }
}

describe('AIConfigPanel', () => {
  it('renders cheap/expensive models, effort, and escalation threshold', () => {
    const wrapper = mount(AIConfigPanel, { props: { config: config() } })

    const text = wrapper.text()
    expect(text).toContain('gpt-4o-mini')
    expect(text).toContain('gpt-4o')
    expect(text).toContain('high')
    expect(text).toContain('0.7')
  })

  it('renders the version with its label', () => {
    const wrapper = mount(AIConfigPanel, { props: { config: config() } })

    expect(wrapper.get('[data-testid="config-version"]').text()).toContain('v3')
    expect(wrapper.get('[data-testid="config-version"]').text()).toContain('tuned-prompt')
  })

  it('renders the version number alone when there is no label', () => {
    const wrapper = mount(AIConfigPanel, { props: { config: config({ label: null }) } })

    const versionText = wrapper.get('[data-testid="config-version"]').text()
    expect(versionText).toContain('v3')
    expect(versionText).not.toContain('·')
  })

  it('shows the system prompt', () => {
    const wrapper = mount(AIConfigPanel, { props: { config: config() } })

    expect(wrapper.find('[data-testid="config-system-prompt"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('You are a metadata extractor.')
  })
})
