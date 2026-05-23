import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatusBadge from '@/components/StatusBadge.vue'
import { FILE_STATUSES, type FileStatus } from '@/types'

interface StatusExpectation {
  status: FileStatus
  pulses: boolean
  // Matches the shadcn Badge variant class fragment we expect to be present.
  variantClass: string
}

const expectations: StatusExpectation[] = [
  { status: 'pending', pulses: false, variantClass: 'bg-secondary' },
  { status: 'reading', pulses: true, variantClass: 'bg-secondary' },
  { status: 'ai_queued', pulses: true, variantClass: 'bg-secondary' },
  { status: 'enriching', pulses: true, variantClass: 'bg-secondary' },
  { status: 'enriched', pulses: false, variantClass: 'bg-primary' },
  { status: 'accepted', pulses: false, variantClass: 'bg-primary' },
  { status: 'rejected', pulses: false, variantClass: 'bg-destructive' },
  { status: 'failed', pulses: false, variantClass: 'bg-destructive' },
]

describe('StatusBadge', () => {
  it.each(expectations)(
    'renders $status with the correct variant and pulse state',
    ({ status, pulses, variantClass }) => {
      const wrapper = mount(StatusBadge, { props: { status } })

      const html = wrapper.html()
      expect(html).toContain(variantClass)
      if (pulses) {
        expect(html).toContain('animate-pulse')
      } else {
        expect(html).not.toContain('animate-pulse')
      }
      expect(wrapper.text()).toBe(status)
    },
  )

  it('covers every FileStatus value (no status falls through to undefined variant)', () => {
    const covered = new Set(expectations.map((e) => e.status))
    for (const status of FILE_STATUSES) {
      expect(covered.has(status)).toBe(true)
    }
  })
})
