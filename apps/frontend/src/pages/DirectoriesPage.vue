<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import DirectoryTreeNode from '@/components/DirectoryTreeNode.vue'
import { listDirectories } from '@/services/api'
import type { DirectoryNode } from '@/types'

const directories = ref<DirectoryNode[]>([])
const loading = ref(true)
const loadError = ref<string | null>(null)

async function load(): Promise<void> {
  loading.value = true
  loadError.value = null
  try {
    directories.value = await listDirectories()
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="space-y-4">
    <header class="space-y-1">
      <h1 class="text-2xl font-bold tracking-tight">Directories</h1>
      <p class="text-muted-foreground">
        Browse scanned directories. Click a directory to view its files, or trigger a scan.
      </p>
    </header>

    <div v-if="loading" class="flex items-center gap-2 text-muted-foreground">
      <Loader2 class="h-4 w-4 animate-spin" />
      <span>Loading directories…</span>
    </div>

    <div
      v-else-if="loadError"
      class="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive"
    >
      Failed to load directories: {{ loadError }}
    </div>

    <div v-else-if="directories.length === 0" class="text-muted-foreground">
      No directories yet. Run a scan to discover them.
    </div>

    <ul v-else class="space-y-1">
      <DirectoryTreeNode
        v-for="node in directories"
        :key="node.id"
        :node="node"
      />
    </ul>
  </section>
</template>
