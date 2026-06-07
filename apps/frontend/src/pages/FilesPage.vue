<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2 } from 'lucide-vue-next'
import StatusBadge from '@/components/StatusBadge.vue'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { getDirectoryDetail } from '@/services/api'
import type { DirectoryDetail, FileStatus } from '@/types'
import { FILE_STATUSES } from '@/types'

const route = useRoute()
const router = useRouter()

const directory = ref<DirectoryDetail | null>(null)
const loading = ref(true)
const loadError = ref<string | null>(null)
const statusFilter = ref<FileStatus | ''>('')

const directoryId = computed<number | null>(() => {
  const raw = route.params.id
  const value = Array.isArray(raw) ? raw[0] : raw
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
})

async function load(): Promise<void> {
  const id = directoryId.value
  if (id === null) {
    loadError.value = 'Invalid directory id in URL'
    loading.value = false
    return
  }

  loading.value = true
  loadError.value = null
  try {
    const filter = statusFilter.value === '' ? undefined : statusFilter.value
    directory.value = await getDirectoryDetail(id, filter)
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

const statusCounts = computed<Array<{ status: FileStatus; count: number }>>(() => {
  const files = directory.value?.files ?? []
  return FILE_STATUSES.map((status) => ({
    status,
    count: files.filter((file) => file.status === status).length,
  })).filter((entry) => entry.count > 0)
})

function openFile(fileId: number): void {
  void router.push({ name: 'file-detail', params: { id: fileId } })
}

onMounted(load)
watch([directoryId, statusFilter], load)
</script>

<template>
  <section class="space-y-4">
    <header class="space-y-1">
      <h1 class="text-2xl font-bold tracking-tight">
        Files
        <span v-if="directory" class="text-muted-foreground font-normal"
          >· {{ directory.name }}</span
        >
      </h1>
      <p v-if="directory" class="text-sm text-muted-foreground">
        {{ directory.path }}
      </p>
    </header>

    <div class="flex items-center gap-3">
      <label for="status-filter" class="text-sm font-medium">Status</label>
      <select
        id="status-filter"
        v-model="statusFilter"
        class="h-9 rounded-md border border-input bg-background px-3 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      >
        <option value="">All</option>
        <option v-for="s in FILE_STATUSES" :key="s" :value="s">{{ s }}</option>
      </select>
    </div>

    <div
      v-if="!loading && !loadError && statusCounts.length > 0"
      class="flex flex-wrap items-center gap-2"
      data-test="status-counts"
    >
      <span
        v-for="entry in statusCounts"
        :key="entry.status"
        class="flex items-center gap-1.5 text-sm"
        :data-test="`status-count-${entry.status}`"
      >
        <StatusBadge :status="entry.status" />
        <span class="tabular-nums text-muted-foreground">{{ entry.count }}</span>
      </span>
    </div>

    <div v-if="loading" class="flex items-center gap-2 text-muted-foreground">
      <Loader2 class="h-4 w-4 animate-spin" />
      <span>Loading files…</span>
    </div>

    <div
      v-else-if="loadError"
      class="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
    >
      Failed to load files: {{ loadError }}
    </div>

    <div v-else-if="!directory || directory.files.length === 0" class="text-muted-foreground">
      No files match the current filter.
    </div>

    <Table v-else>
      <TableHeader>
        <TableRow>
          <TableHead>Filename</TableHead>
          <TableHead>Format</TableHead>
          <TableHead>Status</TableHead>
          <TableHead class="text-right">Sort order</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow
          v-for="file in directory.files"
          :key="file.id"
          class="cursor-pointer"
          @click="openFile(file.id)"
        >
          <TableCell class="font-medium">{{ file.filename }}</TableCell>
          <TableCell>{{ file.format ?? file.extension }}</TableCell>
          <TableCell><StatusBadge :status="file.status" /></TableCell>
          <TableCell class="text-right tabular-nums">
            {{ file.sort_order ?? '—' }}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </section>
</template>
