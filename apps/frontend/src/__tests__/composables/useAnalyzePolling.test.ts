import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  isAnalyzeInFlight,
  isAnalyzeSettled,
  useAnalyzePolling,
} from '@/composables/useAnalyzePolling'
import * as api from '@/services/api'
import type { FileDetail, FileStatus, MetadataSnapshot } from '@/types'

function snapshot(source: MetadataSnapshot['source']): MetadataSnapshot {
  return {
    id: 1,
    source,
    is_current: true,
    title: 'T',
    subtitle: null,
    language: 'en',
    series: null,
    series_index: null,
    isbn13: null,
    confidence: null,
    data: {},
    created_at: '2026-05-23T00:00:00Z',
  }
}

function detail(status: FileStatus, withAi = false): FileDetail {
  return {
    id: 7,
    directory_id: 1,
    filename: 'book.epub',
    extension: '.epub',
    format: 'epub',
    status,
    sort_order: 1.0,
    error_message: null,
    file_metadata: snapshot('file'),
    ai_metadata: withAi ? snapshot('ai') : null,
  }
}

function enrichResponse(status: FileStatus) {
  return { enrichment_run_id: 42, file_id: 7, status }
}

describe('isAnalyzeInFlight / isAnalyzeSettled', () => {
  it.each<[FileStatus, boolean]>([
    ['analyze_queued', true],
    ['ai_queued', true],
    ['enriching', true],
    ['enriched', false],
    ['failed', false],
    ['read', false],
  ])('isAnalyzeInFlight(%s) === %s', (status, expected) => {
    expect(isAnalyzeInFlight(status)).toBe(expected)
  })

  it.each<[FileStatus, boolean]>([
    ['enriched', true],
    ['failed', true],
    ['accepted', true],
    ['rejected', true],
    ['missing', true],
    ['analyze_queued', false],
    ['enriching', false],
  ])('isAnalyzeSettled(%s) === %s', (status, expected) => {
    expect(isAnalyzeSettled(status)).toBe(expected)
  })

  it('treats null/undefined as neither in-flight nor settled', () => {
    expect(isAnalyzeInFlight(null)).toBe(false)
    expect(isAnalyzeSettled(undefined)).toBe(false)
  })
})

describe('useAnalyzePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('triggers enrich, marks analyzing, then polls until enriched', async () => {
    const enrichSpy = vi.spyOn(api, 'enrichFile').mockResolvedValue(enrichResponse('analyze_queued'))
    const detailSpy = vi
      .spyOn(api, 'getFileDetail')
      .mockResolvedValueOnce(detail('enriching'))
      .mockResolvedValueOnce(detail('enriched', true))

    const received: FileDetail[] = []
    const polling = useAnalyzePolling((next) => received.push(next), { pollIntervalMs: 1000 })

    await polling.startAnalyze(7)
    expect(enrichSpy).toHaveBeenCalledWith(7)
    expect(polling.isAnalyzing.value).toBe(true)

    await vi.advanceTimersByTimeAsync(1000)
    expect(polling.isAnalyzing.value).toBe(true)
    expect(received).toHaveLength(1)

    await vi.advanceTimersByTimeAsync(1000)
    expect(detailSpy).toHaveBeenCalledTimes(2)
    expect(received).toHaveLength(2)
    expect(received[1]?.status).toBe('enriched')
    expect(polling.isAnalyzing.value).toBe(false)
  })

  it('stops polling on a failed status', async () => {
    vi.spyOn(api, 'enrichFile').mockResolvedValue(enrichResponse('analyze_queued'))
    const detailSpy = vi.spyOn(api, 'getFileDetail').mockResolvedValue(detail('failed'))

    const polling = useAnalyzePolling(() => {}, { pollIntervalMs: 1000 })
    await polling.startAnalyze(7)
    await vi.advanceTimersByTimeAsync(1000)

    expect(polling.isAnalyzing.value).toBe(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(detailSpy).toHaveBeenCalledTimes(1)
  })

  it('records the error and does not poll when enrich rejects', async () => {
    vi.spyOn(api, 'enrichFile').mockRejectedValue(new Error('queue down'))
    const detailSpy = vi.spyOn(api, 'getFileDetail').mockResolvedValue(detail('enriched', true))

    const polling = useAnalyzePolling(() => {}, { pollIntervalMs: 1000 })
    await polling.startAnalyze(7)

    expect(polling.error.value).toBe('queue down')
    expect(polling.isAnalyzing.value).toBe(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(detailSpy).not.toHaveBeenCalled()
  })

  it('records the error and halts when a poll fetch rejects', async () => {
    vi.spyOn(api, 'enrichFile').mockResolvedValue(enrichResponse('analyze_queued'))
    vi.spyOn(api, 'getFileDetail').mockRejectedValue(new Error('detail 500'))

    const polling = useAnalyzePolling(() => {}, { pollIntervalMs: 1000 })
    await polling.startAnalyze(7)
    await vi.advanceTimersByTimeAsync(1000)

    expect(polling.error.value).toBe('detail 500')
    expect(polling.isAnalyzing.value).toBe(false)
  })

  it('stop() cancels a pending poll', async () => {
    vi.spyOn(api, 'enrichFile').mockResolvedValue(enrichResponse('analyze_queued'))
    const detailSpy = vi.spyOn(api, 'getFileDetail').mockResolvedValue(detail('enriching'))

    const polling = useAnalyzePolling(() => {}, { pollIntervalMs: 1000 })
    await polling.startAnalyze(7)
    polling.stop()

    expect(polling.isAnalyzing.value).toBe(false)
    await vi.advanceTimersByTimeAsync(5000)
    expect(detailSpy).not.toHaveBeenCalled()
  })
})
