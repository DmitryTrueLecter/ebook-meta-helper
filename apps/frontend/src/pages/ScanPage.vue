<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Loader2, ScanLine } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import {
  getScanStatus,
  listDirectories,
  triggerDirectoryScan,
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
const startError = ref<string | null>(null)
const loading = ref(true)
const starting = ref(false)

let pollHandle: ReturnType<typeof setInterval> | null = null

function isActive(status: ScanJobStatus | null): boolean {
  return status !== null && ACTIVE_STATES.includes(status.status)
}

const progressPercent = computed<number>(() => {
  const status = scanStatus.value
  if (status === null || status.files_discovered === 0) {
    return 0
  }
  const ratio = status.files_processed / status.files_discovered
  return Math.min(100, Math.max(0, Math.round(ratio * 100)))
})

function stopPolling(): void {
  if (pollHandle !== null) {
    clearInterval(pollHandle)
    pollHandle = null
  }
}

async function refreshStatus(): Promise<void> {
  try {
    const next = await getScanStatus()
    scanStatus.value = next
    if (!isActive(next)) {
      stopPolling()
    }
  } catch (err) {
    // Surface polling errors but keep the last known progress visible.
    loadError.value = err instanceof Error ? err.message : String(err)
    stopPolling()
  }
}

function startPolling(): void {
  if (pollHandle !== null) {
    return
  }
  pollHandle = setInterval(() => {
    void refreshStatus()
  }, POLL_INTERVAL_MS)
}

async function startScan(): Promise<void> {
  const id = selectedDirectoryId.value
  if (id === null) {
    startError.value = 'Select a directory to scan.'
    return
  }
  starting.value = true
  startError.value = null
  try {
    scanStatus.value = await triggerDirectoryScan(id)
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
      <h1 class="text-2xl font-bold tracking-tight">Scan</h1>
      <p class="text-muted-foreground">
        Trigger a directory scan and watch progress in real time.
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
        <h2 id="scan-launcher-heading" class="text-lg font-semibold">Scan directory</h2>

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
            @click="startScan"
          >
            <Loader2 v-if="starting" class="mr-1 h-3.5 w-3.5 animate-spin" />
            <ScanLine v-else class="mr-1 h-3.5 w-3.5" />
            Start Scan
          </Button>
        </div>

        <p v-if="directories.length === 0" class="text-sm text-muted-foreground">
          No directories discovered yet. Add a directory before scanning.
        </p>

        <p v-if="startError" class="text-sm text-destructive">{{ startError }}</p>
      </section>

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

        <p
          v-else-if="scanStatus.status === 'failed'"
          class="text-sm text-destructive"
          data-test="scan-failed-summary"
        >
          Scan failed at file {{ scanStatus.files_processed }} of
          {{ scanStatus.files_discovered }}.
        </p>
      </section>
    </template>
  </section>
</template>
