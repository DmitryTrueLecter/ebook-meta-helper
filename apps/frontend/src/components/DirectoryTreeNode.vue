<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, ChevronRight, FolderClosed, Loader2, ScanLine } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { triggerDirectoryScan } from '@/services/api'
import type { DirectoryNode } from '@/types'

interface Props {
  node: DirectoryNode
}

const props = defineProps<Props>()
const router = useRouter()

const expanded = ref(true)
const scanning = ref(false)
const scanError = ref<string | null>(null)

function toggle(): void {
  expanded.value = !expanded.value
}

function openFiles(): void {
  void router.push({ name: 'files', params: { id: props.node.id } })
}

async function startScan(): Promise<void> {
  scanning.value = true
  scanError.value = null
  try {
    await triggerDirectoryScan(props.node.id)
    await router.push({ name: 'scan' })
  } catch (err) {
    scanError.value = err instanceof Error ? err.message : String(err)
  } finally {
    scanning.value = false
  }
}
</script>

<template>
  <li class="space-y-1">
    <div class="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted/50">
      <button
        v-if="node.children.length > 0"
        type="button"
        class="flex h-5 w-5 items-center justify-center text-muted-foreground hover:text-foreground"
        :aria-label="expanded ? 'Collapse' : 'Expand'"
        @click="toggle"
      >
        <ChevronDown v-if="expanded" class="h-4 w-4" />
        <ChevronRight v-else class="h-4 w-4" />
      </button>
      <span v-else class="inline-block h-5 w-5" aria-hidden="true" />

      <FolderClosed class="h-4 w-4 text-muted-foreground" />

      <button
        type="button"
        class="flex-1 text-left font-medium hover:underline"
        @click="openFiles"
      >
        {{ node.name }}
      </button>

      <div class="flex items-center gap-2">
        <Badge variant="secondary">{{ node.file_count }} files</Badge>
        <Badge variant="outline" class="border-yellow-300 bg-yellow-50 text-yellow-800">
          {{ node.enriched_count }} enriched
        </Badge>
        <Badge variant="outline" class="border-gray-300 bg-gray-50 text-gray-700">
          {{ node.pending_count }} pending
        </Badge>
        <Badge variant="outline" class="border-green-300 bg-green-50 text-green-800">
          {{ node.accepted_count }} accepted
        </Badge>
        <Button
          variant="outline"
          size="sm"
          :disabled="scanning"
          @click="startScan"
        >
          <Loader2 v-if="scanning" class="mr-1 h-3.5 w-3.5 animate-spin" />
          <ScanLine v-else class="mr-1 h-3.5 w-3.5" />
          Scan
        </Button>
      </div>
    </div>

    <p v-if="scanError" class="pl-7 text-sm text-destructive">{{ scanError }}</p>

    <ul v-if="expanded && node.children.length > 0" class="ml-6 space-y-1 border-l pl-2">
      <DirectoryTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
      />
    </ul>
  </li>
</template>
