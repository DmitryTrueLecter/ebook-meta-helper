import { readonly, ref } from 'vue'

import { ApiError, enrichFile, getFileDetail } from '@/services/api'
import type { FileDetail, FileStatus } from '@/types'

// Terminal statuses for an analyze run (success, failure, user decision, or file gone).
const SETTLED_STATUSES = new Set<FileStatus>([
  'enriched',
  'failed',
  'accepted',
  'rejected',
  'missing',
])

// Statuses that mean an analyze run is still in flight — keep polling.
const IN_FLIGHT_STATUSES = new Set<FileStatus>(['analyze_queued', 'ai_queued', 'enriching'])

// Statuses the backend accepts for POST /enrich (analyze / re-analyze); mirrors file_repo._ALLOWED_TRANSITIONS.
const ANALYZE_ALLOWED_STATUSES = new Set<FileStatus>([
  'read',
  'enriched',
  'accepted',
  'rejected',
  'failed',
])

export const ANALYZE_POLL_INTERVAL_MS = 2000

export interface AnalyzePollingOptions {
  pollIntervalMs?: number
}

export function isAnalyzeInFlight(status: FileStatus | null | undefined): boolean {
  return status !== null && status !== undefined && IN_FLIGHT_STATUSES.has(status)
}

export function isAnalyzeAllowed(status: FileStatus | null | undefined): boolean {
  return status !== null && status !== undefined && ANALYZE_ALLOWED_STATUSES.has(status)
}

export function isAnalyzeSettled(status: FileStatus | null | undefined): boolean {
  return status !== null && status !== undefined && SETTLED_STATUSES.has(status)
}

// Owns one analyze run: trigger enrich, then poll getFileDetail (handing each fresh detail to onDetail) until the file leaves the in-flight set.
export function useAnalyzePolling(
  onDetail: (detail: FileDetail) => void,
  options: AnalyzePollingOptions = {},
) {
  const pollIntervalMs = options.pollIntervalMs ?? ANALYZE_POLL_INTERVAL_MS
  const analyzing = ref(false)
  const error = ref<string | null>(null)
  // True when the last startAnalyze was rejected with 409 — the file's status drifted out of the allowed set.
  const conflicted = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  const isAnalyzing = readonly(analyzing)

  function clearTimer(): void {
    if (timer !== null) {
      clearTimeout(timer)
      timer = null
    }
  }

  function scheduleNextPoll(fileId: number): void {
    timer = setTimeout(() => {
      void pollOnce(fileId)
    }, pollIntervalMs)
  }

  async function pollOnce(fileId: number): Promise<void> {
    let detail: FileDetail
    try {
      detail = await getFileDetail(fileId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      analyzing.value = false
      clearTimer()
      return
    }
    onDetail(detail)
    if (isAnalyzeInFlight(detail.status)) {
      scheduleNextPoll(fileId)
      return
    }
    // A non-in-flight, non-settled status (e.g. job rolled back to `read`) is unexpected — surface it so the loop ends instead of hanging.
    if (!isAnalyzeSettled(detail.status)) {
      error.value = `Analyze run ended in unexpected status "${detail.status}".`
    }
    analyzing.value = false
    clearTimer()
  }

  async function startAnalyze(fileId: number): Promise<void> {
    error.value = null
    conflicted.value = false
    clearTimer()
    try {
      await enrichFile(fileId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
      conflicted.value = err instanceof ApiError && err.status === 409
      return
    }
    analyzing.value = true
    scheduleNextPoll(fileId)
  }

  function stop(): void {
    clearTimer()
    analyzing.value = false
  }

  return {
    isAnalyzing,
    error: readonly(error),
    conflicted: readonly(conflicted),
    startAnalyze,
    stop,
  }
}
