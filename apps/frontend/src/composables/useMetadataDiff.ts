import type { JsonValue, MetadataSnapshot } from '@/types'

// Highlight is one-sided (applied to the AI cell): 'changed' = both differ; 'new' = file empty + AI present; 'none' = same or AI empty.
export type DiffHighlight = 'none' | 'changed' | 'new'

export interface DiffRow {
  label: string
  key: string
  fileValue: string
  aiValue: string
  highlight: DiffHighlight
}

// Scalar columns exposed on MetadataSnapshot itself.
interface ScalarFieldSpec {
  label: string
  pick: (snap: MetadataSnapshot) => string | number | null
}

const SCALAR_FIELDS: ReadonlyArray<readonly [string, ScalarFieldSpec]> = [
  ['title', { label: 'Title', pick: (s) => s.title }],
  ['subtitle', { label: 'Subtitle', pick: (s) => s.subtitle }],
  ['series', { label: 'Series', pick: (s) => s.series }],
  ['series_index', { label: 'Series #', pick: (s) => s.series_index }],
  ['language', { label: 'Language', pick: (s) => s.language }],
  ['isbn13', { label: 'ISBN-13', pick: (s) => s.isbn13 }],
] as const

// Keys inside `data` that we render as named rows. Anything else stays in `data`
// but is not surfaced — those are not part of the review contract.
const DATA_FIELDS: ReadonlyArray<readonly [string, string]> = [
  ['authors', 'Authors'],
  ['tags', 'Tags'],
  ['description', 'Description'],
] as const

export function formatValue(value: JsonValue | string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return ''
  }
  if (Array.isArray(value)) {
    return value.map((item) => formatValue(item)).join(', ')
  }
  if (typeof value === 'object') {
    return JSON.stringify(value)
  }
  return String(value)
}

function isEmpty(formatted: string): boolean {
  return formatted.trim() === ''
}

function computeHighlight(fileFormatted: string, aiFormatted: string): DiffHighlight {
  if (isEmpty(aiFormatted)) {
    return 'none'
  }
  if (isEmpty(fileFormatted)) {
    return 'new'
  }
  return fileFormatted === aiFormatted ? 'none' : 'changed'
}

function buildScalarRow(
  key: string,
  spec: ScalarFieldSpec,
  file: MetadataSnapshot | null,
  ai: MetadataSnapshot | null,
): DiffRow {
  const fileValue = formatValue(file ? spec.pick(file) : null)
  const aiValue = formatValue(ai ? spec.pick(ai) : null)
  return {
    label: spec.label,
    key,
    fileValue,
    aiValue,
    highlight: computeHighlight(fileValue, aiValue),
  }
}

function buildDataRow(
  key: string,
  label: string,
  file: MetadataSnapshot | null,
  ai: MetadataSnapshot | null,
): DiffRow {
  const fileValue = formatValue(file?.data[key] ?? null)
  const aiValue = formatValue(ai?.data[key] ?? null)
  return {
    label,
    key,
    fileValue,
    aiValue,
    highlight: computeHighlight(fileValue, aiValue),
  }
}

// Emit one row per field even when both sides are empty so layout stays stable across files.
export function buildDiffRows(
  file: MetadataSnapshot | null,
  ai: MetadataSnapshot | null,
): DiffRow[] {
  const rows: DiffRow[] = []
  for (const [key, spec] of SCALAR_FIELDS) {
    rows.push(buildScalarRow(key, spec, file, ai))
  }
  for (const [key, label] of DATA_FIELDS) {
    rows.push(buildDataRow(key, label, file, ai))
  }
  return rows
}
