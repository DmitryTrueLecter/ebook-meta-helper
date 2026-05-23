import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import StatusBadge from '@/components/StatusBadge.vue'
import { FILE_STATUSES, type FileStatus } from '@/types'

interface StatusExpectation {
  status: FileStatus
  classes: string[]
  forbidden?: string[]
  label: string
}

const expectations: StatusExpectation[] = [
  { status: 'pending', classes: ['bg-gray-200', 'text-gray-800'], forbidden: ['animate-pulse', 'line-through'], label: 'pending' },
  { status: 'reading', classes: ['bg-blue-100', 'text-blue-800', 'animate-pulse'], label: 'reading' },
  { status: 'ai_queued', classes: ['bg-blue-100', 'text-blue-800', 'animate-pulse'], label: 'AI queued' },
  { status: 'enriching', classes: ['bg-blue-100', 'text-blue-800', 'animate-pulse'], label: 'enriching' },
  { status: 'enriched', classes: ['bg-yellow-100', 'text-yellow-800'], forbidden: ['animate-pulse', 'line-through'], label: 'enriched' },
  { status: 'accepted', classes: ['bg-green-100', 'text-green-800'], forbidden: ['line-through'], label: 'accepted' },
  { status: 'rejected', classes: ['bg-gray-200', 'text-gray-600', 'line-through'], label: 'rejected' },
  { status: 'failed', classes: ['bg-red-100', 'text-red-800'], forbidden: ['animate-pulse'], label: 'failed' },
]

describe('StatusBadge', () => {
  it.each(expectations)(
    'renders $status with the correct colour classes and label',
    ({ status, classes, forbidden, label }) => {
      const wrapper = mount(StatusBadge, { props: { status } })

      const rendered = wrapper.html()
      for (const cls of classes) {
        expect(rendered).toContain(cls)
      }
      for (const cls of forbidden ?? []) {
        expect(rendered).not.toContain(cls)
      }
      expect(wrapper.text()).toBe(label)
    },
  )

  it('covers every FileStatus value (no status falls through to "undefined" classes)', () => {
    const covered = new Set(expectations.map((e) => e.status))
    for (const status of FILE_STATUSES) {
      expect(covered.has(status)).toBe(true)
    }
  })
})
