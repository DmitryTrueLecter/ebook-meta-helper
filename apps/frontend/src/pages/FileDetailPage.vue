<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import MetadataDiffPanel from '@/components/MetadataDiffPanel.vue'
import ProcessingLogTimeline from '@/components/ProcessingLogTimeline.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { Button } from '@/components/ui/button'
import { buildDiffRows } from '@/composables/useMetadataDiff'
import {
  acceptFile,
  enrichFile,
  getFileDetail,
  getFileLogs,
  rejectFile,
} from '@/services/api'
import type { FileDetail, FileStatus, ProcessingLogEntry } from '@/types'

type ToastTone = 'success' | 'info' | 'error'

interface Toast {
  tone: ToastTone
  message: string
}

const route = useRoute()

const rawId = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
const fileId = Number.parseInt(rawId ?? '', 10)
const fileIdValid = Number.isFinite(fileId) && fileId > 0

const detail = ref<FileDetail | null>(null)
const logs = ref<ProcessingLogEntry[]>([])
const loadingDetail = ref(false)
const loadingLogs = ref(false)
const detailError = ref<string | null>(null)
const logsError = ref<string | null>(null)
const actionInFlight = ref<'accept' | 'reject' | 'enrich' | null>(null)
const showLogs = ref(false)
const toast = ref<Toast | null>(null)

const diffRows = computed(() =>
  buildDiffRows(detail.value?.file_metadata ?? null, detail.value?.ai_metadata ?? null),
)
const hasAi = computed(
  () => detail.value?.ai_metadata !== null && detail.value?.ai_metadata !== undefined,
)
const hasFile = computed(
  () => detail.value?.file_metadata !== null && detail.value?.file_metadata !== undefined,
)
const status = computed(() => detail.value?.status ?? null)

// Terminal statuses disable Accept/Reject — re-running AI is always allowed.
const TERMINAL_STATUSES = new Set<FileStatus>(['accepted', 'rejected'])
const decisionDisabled = computed(() => {
  if (!detail.value) {
    return true
  }
  if (!hasAi.value) {
    return true
  }
  if (actionInFlight.value !== null) {
    return true
  }
  return TERMINAL_STATUSES.has(detail.value.status)
})

const enrichDisabled = computed(() => {
  if (!detail.value) {
    return true
  }
  return actionInFlight.value !== null
})

function flashToast(tone: ToastTone, message: string): void {
  toast.value = { tone, message }
  window.setTimeout(() => {
    if (toast.value?.message === message) {
      toast.value = null
    }
  }, 4000)
}

async function loadDetail(): Promise<void> {
  if (!fileIdValid) {
    return
  }
  loadingDetail.value = true
  detailError.value = null
  try {
    detail.value = await getFileDetail(fileId)
  } catch (err) {
    detailError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loadingDetail.value = false
  }
}

async function loadLogs(): Promise<void> {
  if (!fileIdValid) {
    return
  }
  loadingLogs.value = true
  logsError.value = null
  try {
    logs.value = await getFileLogs(fileId)
  } catch (err) {
    logsError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loadingLogs.value = false
  }
}

async function toggleLogs(): Promise<void> {
  showLogs.value = !showLogs.value
  if (showLogs.value && logs.value.length === 0 && logsError.value === null) {
    await loadLogs()
  }
}

async function runAction(
  kind: 'accept' | 'reject' | 'enrich',
  call: (id: number) => Promise<{ status: FileStatus }>,
  successMessage: string,
  successTone: ToastTone,
): Promise<void> {
  if (!fileIdValid) {
    return
  }
  actionInFlight.value = kind
  try {
    const response = await call(fileId)
    if (detail.value !== null) {
      detail.value = { ...detail.value, status: response.status }
    }
    flashToast(successTone, successMessage)
    await loadDetail()
  } catch (err) {
    flashToast('error', err instanceof Error ? err.message : String(err))
  } finally {
    actionInFlight.value = null
  }
}

async function onAccept(): Promise<void> {
  await runAction('accept', acceptFile, 'Accepted AI suggestion', 'success')
}

async function onReject(): Promise<void> {
  await runAction('reject', rejectFile, 'Rejected AI suggestion', 'info')
}

async function onEnrich(): Promise<void> {
  await runAction('enrich', enrichFile, 'Re-running AI enrichment', 'info')
}

onMounted(loadDetail)

const toastClasses: Record<ToastTone, string> = {
  success: 'bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100',
  info: 'bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-100',
  error: 'bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-100',
}
</script>

<template>
  <section class="space-y-6">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div class="space-y-1">
        <h1 class="text-2xl font-bold tracking-tight">File detail</h1>
        <p class="text-sm text-muted-foreground">File #{{ rawId }}</p>
      </div>
      <StatusBadge v-if="status" :status="status" />
    </header>

    <div
      v-if="toast"
      role="status"
      :class="['rounded-md px-3 py-2 text-sm', toastClasses[toast.tone]]"
    >
      {{ toast.message }}
    </div>

    <p v-if="!fileIdValid" class="text-sm text-destructive">Invalid file id.</p>
    <p v-else-if="loadingDetail" class="text-sm text-muted-foreground">Loading metadata…</p>
    <p v-else-if="detailError" class="text-sm text-destructive">{{ detailError }}</p>

    <div v-if="detail" class="grid gap-4 md:grid-cols-2">
      <MetadataDiffPanel
        title="Original (file)"
        side="file"
        :rows="diffRows"
        :is-empty="!hasFile"
        empty-message="No metadata read from file yet."
      />
      <MetadataDiffPanel
        title="AI suggestion"
        side="ai"
        :rows="diffRows"
        :is-empty="!hasAi"
        empty-message="AI has not produced a suggestion yet."
      />
    </div>

    <div v-if="detail" class="flex flex-wrap gap-2">
      <Button variant="default" :disabled="decisionDisabled" @click="onAccept">
        {{ actionInFlight === 'accept' ? 'Accepting…' : 'Accept' }}
      </Button>
      <Button variant="destructive" :disabled="decisionDisabled" @click="onReject">
        {{ actionInFlight === 'reject' ? 'Rejecting…' : 'Reject' }}
      </Button>
      <Button variant="secondary" :disabled="enrichDisabled" @click="onEnrich">
        {{ actionInFlight === 'enrich' ? 'Queuing…' : 'Re-run AI' }}
      </Button>
    </div>

    <section v-if="detail" class="space-y-3">
      <Button variant="ghost" @click="toggleLogs">
        {{ showLogs ? 'Hide processing log' : 'Show processing log' }}
      </Button>
      <div v-if="showLogs" class="space-y-2">
        <p v-if="loadingLogs" class="text-sm text-muted-foreground">Loading log…</p>
        <p v-else-if="logsError" class="text-sm text-destructive">{{ logsError }}</p>
        <p v-else-if="logs.length === 0" class="text-sm text-muted-foreground">
          No processing log entries yet.
        </p>
        <ProcessingLogTimeline v-else :entries="logs" />
      </div>
    </section>
  </section>
</template>
