import { computed, readonly, ref } from 'vue'

import { enrichFile, getFileDetail } from '@/services/api'
import type { FileDetail, FileStatus } from '@/types'

// Statuses at which polling stops: the analyze run has settled (or the file is gone).
const SETTLED_STATUSES = new Set<FileStatus>([
  'enriched',
  'failed',
  'accepted',
  'rejected',
  'missing',
])

// Statuses that mean an analyze run is still in flight — keep polling.
const IN_FLIGHT_STATUSES = new Set<FileStatus>(['analyze_queued', 'ai_queued', 'enriching'])

export const ANALYZE_POLL_INTERVAL_MS = 2000

export interface AnalyzePollingOptions {
  pollIntervalMs?: number
}

export function isAnalyzeInFlight(status: FileStatus | null | undefined): boolean {
  return status !== null && status !== undefined && IN_FLIGHT_STATUSES.has(status)
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
  let timer: ReturnType<typeof setTimeout> | null = null

  const isAnalyzing = computed(() => analyzing.value)

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
    if (isAnalyzeSettled(detail.status)) {
      analyzing.value = false
      clearTimer()
      return
    }
    scheduleNextPoll(fileId)
  }

  async function startAnalyze(fileId: number): Promise<void> {
    error.value = null
    clearTimer()
    try {
      await enrichFile(fileId)
    } catch (err) {
      error.value = err instanceof Error ? err.message : String(err)
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
    startAnalyze,
    stop,
  }
}
