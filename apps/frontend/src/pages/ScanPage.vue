<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Loader2, RefreshCw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  discoverDirectory,
  getScanStatus,
  listDirectories,
} from '@/services/api'
import type { DirectoryNode, ScanJobState, ScanJobStatus } from '@/types'

const POLL_INTERVAL_MS = 2000
const ACTIVE_STATES: ReadonlyArray<ScanJobState> = ['pending', 'running']

interface DirectoryOption {
  id: number
  label: string
}

function flattenDirectories(nodes: DirectoryNode[], prefix = ''): DirectoryOption[] {
  const flat: DirectoryOption[] = []
  for (const node of nodes) {
    const label = prefix === '' ? node.name : `${prefix} / ${node.name}`
    flat.push({ id: node.id, label })
    if (node.children.length > 0) {
      flat.push(...flattenDirectories(node.children, label))
    }
  }
  return flat
}

const directories = ref<DirectoryOption[]>([])
const selectedDirectoryId = ref<number | null>(null)
const scanStatus = ref<ScanJobStatus | null>(null)
const loadError = ref<string | null>(null)
const pollError = ref<string | null>(null)
const startError = ref<string | null>(null)
const loading = ref(true)
const starting = ref(false)

let pollHandle: ReturnType<typeof setTimeout> | null = null
let pollingActive = false

function isActive(status: ScanJobStatus | null): boolean {
  return status !== null && ACTIVE_STATES.includes(status.status)
}

const FALLBACK_FAILURE_REASON = 'Scan failed for an unknown reason.'

const failureReason = computed<string>(() => {
  const message = scanStatus.value?.error_message
  return message !== null && message !== undefined && message !== ''
    ? message
    : FALLBACK_FAILURE_REASON
})

const progressPercent = computed<number>(() => {
  const status = scanStatus.value
  if (status === null || status.files_discovered === 0) {
    return 0
  }
  const ratio = status.files_processed / status.files_discovered
  return Math.min(100, Math.max(0, Math.round(ratio * 100)))
})

function stopPolling(): void {
  pollingActive = false
  if (pollHandle !== null) {
    clearTimeout(pollHandle)
    pollHandle = null
  }
}

async function pollOnce(): Promise<void> {
  pollHandle = null
  try {
    const next = await getScanStatus()
    scanStatus.value = next
    pollError.value = null
    if (!isActive(next)) {
      stopPolling()
      return
    }
  } catch (err) {
    // A transient poll failure must not nuke the page — surface inline and stop polling.
    pollError.value = err instanceof Error ? err.message : String(err)
    stopPolling()
    return
  }
  if (pollingActive) {
    pollHandle = setTimeout(() => {
      void pollOnce()
    }, POLL_INTERVAL_MS)
  }
}

function startPolling(): void {
  if (pollingActive) {
    return
  }
  pollingActive = true
  pollError.value = null
  pollHandle = setTimeout(() => {
    void pollOnce()
  }, POLL_INTERVAL_MS)
}

async function startDiscover(): Promise<void> {
  const id = selectedDirectoryId.value
  if (id === null) {
    startError.value = 'Select a directory to discover.'
    return
  }
  starting.value = true
  startError.value = null
  try {
    scanStatus.value = await discoverDirectory(id)
    if (isActive(scanStatus.value)) {
      startPolling()
    }
  } catch (err) {
    startError.value = err instanceof Error ? err.message : String(err)
  } finally {
    starting.value = false
  }
}

onMounted(async () => {
  loading.value = true
  loadError.value = null
  try {
    const [tree, status] = await Promise.all([listDirectories(), getScanStatus()])
    directories.value = flattenDirectories(tree)
    scanStatus.value = status
    if (isActive(status)) {
      startPolling()
    }
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <section class="space-y-6">
    <header class="space-y-1">
      <h1 class="text-2xl font-bold tracking-tight">Discover</h1>
      <p class="text-muted-foreground">
        Discover a directory — find and refresh its files (no AI) — and watch progress in real time.
      </p>
    </header>

    <div v-if="loading" class="flex items-center gap-2 text-muted-foreground">
      <Loader2 class="h-4 w-4 animate-spin" />
      <span>Loading scan state…</span>
    </div>

    <div
      v-else-if="loadError"
      class="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
    >
      Failed to load scan state: {{ loadError }}
    </div>

    <template v-else>
      <section
        aria-labelledby="scan-launcher-heading"
        class="space-y-3 rounded-md border p-4"
      >
        <h2 id="scan-launcher-heading" class="text-lg font-semibold">Discover directory</h2>

        <div class="flex flex-wrap items-center gap-3">
          <label for="scan-directory" class="text-sm font-medium">Directory</label>
          <select
            id="scan-directory"
            v-model="selectedDirectoryId"
            :disabled="directories.length === 0 || starting"
            class="h-9 min-w-[16rem] rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option :value="null" disabled>Select a directory…</option>
            <option v-for="opt in directories" :key="opt.id" :value="opt.id">
              {{ opt.label }}
            </option>
          </select>

          <Button
            type="button"
            :disabled="selectedDirectoryId === null || starting"
            @click="startDiscover"
          >
            <Loader2 v-if="starting" class="mr-1 h-3.5 w-3.5 animate-spin" />
            <RefreshCw v-else class="mr-1 h-3.5 w-3.5" />
            Start Discover
          </Button>
        </div>

        <p v-if="directories.length === 0" class="text-sm text-muted-foreground">
          No directories yet. Add a directory before running Discover.
        </p>

        <p v-if="startError" class="text-sm text-destructive">{{ startError }}</p>
      </section>

      <div
        v-if="pollError"
        class="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive"
        data-test="scan-poll-error"
      >
        Live updates paused: {{ pollError }}
      </div>

      <section
        v-if="scanStatus !== null"
        aria-labelledby="scan-progress-heading"
        class="space-y-2 rounded-md border p-4"
      >
        <h2 id="scan-progress-heading" class="text-lg font-semibold">Progress</h2>

        <dl class="grid gap-y-1 text-sm sm:grid-cols-[10rem_1fr]">
          <dt class="text-muted-foreground">Files discovered</dt>
          <dd class="tabular-nums">{{ scanStatus.files_discovered }}</dd>

          <dt class="text-muted-foreground">Files processed</dt>
          <dd class="tabular-nums">
            {{ scanStatus.files_processed }} / {{ scanStatus.files_discovered }}
          </dd>

          <dt class="text-muted-foreground">Currently</dt>
          <dd class="truncate">{{ scanStatus.current_filename ?? '—' }}</dd>

          <dt class="text-muted-foreground">Status</dt>
          <dd>
            <span
              :data-test="`scan-status-${scanStatus.status}`"
              class="inline-block rounded px-2 py-0.5 text-xs font-medium"
              :class="{
                'bg-blue-100 text-blue-800': scanStatus.status === 'running' || scanStatus.status === 'pending',
                'bg-green-100 text-green-800': scanStatus.status === 'done',
                'bg-red-100 text-red-800': scanStatus.status === 'failed',
                'bg-gray-200 text-gray-700': scanStatus.status === 'cancelled',
              }"
            >
              {{ scanStatus.status }}
            </span>
          </dd>
        </dl>

        <div
          class="h-2 w-full overflow-hidden rounded-full bg-muted"
          role="progressbar"
          :aria-valuenow="progressPercent"
          aria-valuemin="0"
          aria-valuemax="100"
        >
          <!-- Inline style required: Tailwind compiles class names at build time, so a 0–100 runtime width cannot be expressed as a utility class. -->
          <div
            class="h-full bg-primary transition-all"
            :style="{ width: `${progressPercent}%` }"
          />
        </div>

        <p
          v-if="scanStatus.status === 'done'"
          class="text-sm text-green-700"
          data-test="scan-done-summary"
        >
          Scan complete — {{ scanStatus.files_processed }} of
          {{ scanStatus.files_discovered }} files processed.
        </p>

        <div
          v-else-if="scanStatus.status === 'failed'"
          class="space-y-1 text-sm text-destructive"
          data-test="scan-failed-summary"
        >
          <p>
            Scan failed at file {{ scanStatus.files_processed }} of
            {{ scanStatus.files_discovered }}.
          </p>
          <pre
            class="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md border border-destructive/50 bg-destructive/10 p-2 font-mono text-xs"
            data-test="scan-failed-reason"
          >{{ failureReason }}</pre>
        </div>
      </section>
    </template>
  </section>
</template>
