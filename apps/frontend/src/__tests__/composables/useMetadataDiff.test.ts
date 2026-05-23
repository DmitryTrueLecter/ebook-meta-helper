import { describe, expect, it } from 'vitest'

import { buildDiffRows, formatValue } from '@/composables/useMetadataDiff'
import type { MetadataSnapshot } from '@/types'

function snapshot(overrides: Partial<MetadataSnapshot> = {}): MetadataSnapshot {
  return {
    id: 1,
    source: 'file',
    is_current: true,
    title: null,
    subtitle: null,
    language: null,
    series: null,
    series_index: null,
    isbn13: null,
    confidence: null,
    data: {},
    created_at: '2026-05-23T00:00:00Z',
    ...overrides,
  }
}

describe('formatValue', () => {
  it('returns empty string for null', () => {
    expect(formatValue(null)).toBe('')
  })

  it('returns empty string for undefined', () => {
    expect(formatValue(undefined)).toBe('')
  })

  it('returns the string itself for a string value', () => {
    expect(formatValue('Hello')).toBe('Hello')
  })

  it('stringifies numbers', () => {
    expect(formatValue(42)).toBe('42')
    expect(formatValue(0)).toBe('0')
  })

  it('stringifies booleans', () => {
    expect(formatValue(true)).toBe('true')
    expect(formatValue(false)).toBe('false')
  })

  it('joins arrays with ", " by recursively formatting items', () => {
    expect(formatValue(['Asimov', 'Clarke'])).toBe('Asimov, Clarke')
  })

  it('returns empty string for an empty array', () => {
    expect(formatValue([])).toBe('')
  })

  it('JSON-stringifies object values', () => {
    expect(formatValue({ a: 1 })).toBe('{"a":1}')
  })
})

describe('buildDiffRows', () => {
  it('returns a row per scalar+data field even when both snapshots are null', () => {
    const rows = buildDiffRows(null, null)

    // 6 scalar fields + 3 data-dict fields = 9 stable rows.
    expect(rows).toHaveLength(9)
    for (const row of rows) {
      expect(row.fileValue).toBe('')
      expect(row.aiValue).toBe('')
      expect(row.highlight).toBe('none')
    }
  })

  it('marks "changed" when both sides have different values', () => {
    const file = snapshot({ title: 'Old Title' })
    const ai = snapshot({ source: 'ai', title: 'New Title' })

    const rows = buildDiffRows(file, ai)
    const titleRow = rows.find((r) => r.key === 'title')

    expect(titleRow).toBeDefined()
    expect(titleRow?.highlight).toBe('changed')
    expect(titleRow?.fileValue).toBe('Old Title')
    expect(titleRow?.aiValue).toBe('New Title')
  })

  it('marks "new" when file is empty but AI has a value', () => {
    const file = snapshot({ title: null })
    const ai = snapshot({ source: 'ai', title: 'Brand New' })

    const rows = buildDiffRows(file, ai)
    const titleRow = rows.find((r) => r.key === 'title')

    expect(titleRow?.highlight).toBe('new')
  })

  it('marks "none" when both sides match', () => {
    const file = snapshot({ title: 'Same' })
    const ai = snapshot({ source: 'ai', title: 'Same' })

    const rows = buildDiffRows(file, ai)
    const titleRow = rows.find((r) => r.key === 'title')

    expect(titleRow?.highlight).toBe('none')
  })

  it('marks "none" when AI is empty (no highlight even if file is filled)', () => {
    const file = snapshot({ title: 'Only in file' })
    const ai = snapshot({ source: 'ai', title: null })

    const rows = buildDiffRows(file, ai)
    const titleRow = rows.find((r) => r.key === 'title')

    expect(titleRow?.highlight).toBe('none')
    expect(titleRow?.fileValue).toBe('Only in file')
    expect(titleRow?.aiValue).toBe('')
  })

  it('reads data-dict keys (authors/tags/description) for both sides', () => {
    const file = snapshot({ data: { authors: ['Asimov'], tags: ['scifi'] } })
    const ai = snapshot({
      source: 'ai',
      data: { authors: ['Isaac Asimov'], tags: ['scifi'], description: 'A novel.' },
    })

    const rows = buildDiffRows(file, ai)
    const authorsRow = rows.find((r) => r.key === 'authors')
    const tagsRow = rows.find((r) => r.key === 'tags')
    const descRow = rows.find((r) => r.key === 'description')

    expect(authorsRow?.fileValue).toBe('Asimov')
    expect(authorsRow?.aiValue).toBe('Isaac Asimov')
    expect(authorsRow?.highlight).toBe('changed')

    expect(tagsRow?.highlight).toBe('none')

    expect(descRow?.highlight).toBe('new')
    expect(descRow?.aiValue).toBe('A novel.')
  })

  it('formats numeric scalars (series_index) without crashing', () => {
    const file = snapshot({ series_index: 1 })
    const ai = snapshot({ source: 'ai', series_index: 2 })

    const rows = buildDiffRows(file, ai)
    const row = rows.find((r) => r.key === 'series_index')

    expect(row?.fileValue).toBe('1')
    expect(row?.aiValue).toBe('2')
    expect(row?.highlight).toBe('changed')
  })

  it('handles missing data-dict keys without throwing', () => {
    const file = snapshot({ data: {} })
    const ai = snapshot({ source: 'ai', data: {} })

    const rows = buildDiffRows(file, ai)
    const descRow = rows.find((r) => r.key === 'description')

    expect(descRow?.fileValue).toBe('')
    expect(descRow?.aiValue).toBe('')
    expect(descRow?.highlight).toBe('none')
  })

  it('treats null file snapshot like an empty one (no crash)', () => {
    const ai = snapshot({ source: 'ai', title: 'Suggested' })

    const rows = buildDiffRows(null, ai)
    const titleRow = rows.find((r) => r.key === 'title')

    expect(titleRow?.fileValue).toBe('')
    expect(titleRow?.aiValue).toBe('Suggested')
    expect(titleRow?.highlight).toBe('new')
  })

  it('treats null ai snapshot like an empty one (no crash)', () => {
    const file = snapshot({ title: 'In file' })

    const rows = buildDiffRows(file, null)
    const titleRow = rows.find((r) => r.key === 'title')

    expect(titleRow?.fileValue).toBe('In file')
    expect(titleRow?.aiValue).toBe('')
    expect(titleRow?.highlight).toBe('none')
  })
})
