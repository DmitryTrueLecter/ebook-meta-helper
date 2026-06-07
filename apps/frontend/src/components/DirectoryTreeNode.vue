<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ChevronDown, ChevronRight, FolderClosed, Loader2, RefreshCw } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { discoverDirectory } from '@/services/api'
import type { DirectoryNode } from '@/types'

interface Props {
  node: DirectoryNode
}

const props = defineProps<Props>()
const router = useRouter()

const expanded = ref(true)
const discovering = ref(false)
const discoverError = ref<string | null>(null)

const isMissing = computed(() => props.node.status === 'missing')

const visibleChildren = computed<DirectoryNode[]>(() =>
  props.node.children.filter((child) => child.status !== 'missing'),
)

function toggle(): void {
  expanded.value = !expanded.value
}

function openFiles(): void {
  void router.push({ name: 'files', params: { id: props.node.id } })
}

async function startDiscover(): Promise<void> {
  discovering.value = true
  discoverError.value = null
  try {
    await discoverDirectory(props.node.id)
    await router.push({ name: 'scan' })
  } catch (err) {
    discoverError.value = err instanceof Error ? err.message : String(err)
  } finally {
    discovering.value = false
  }
}
</script>

<template>
  <li class="space-y-1">
    <div class="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted/50">
      <button
        v-if="visibleChildren.length > 0"
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
        :class="{ 'text-muted-foreground line-through': isMissing }"
        @click="openFiles"
      >
        {{ node.name }}
      </button>

      <div class="flex items-center gap-2">
        <Badge
          v-if="isMissing"
          variant="outline"
          class="border-orange-300 bg-orange-50 text-orange-800"
          data-test="directory-missing-badge"
        >
          missing
        </Badge>
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
        <Badge
          v-if="node.missing_count > 0"
          variant="outline"
          class="border-orange-300 bg-orange-50 text-orange-800"
          data-test="directory-missing-count"
        >
          {{ node.missing_count }} missing
        </Badge>
        <Button
          variant="outline"
          size="sm"
          :disabled="discovering"
          @click="startDiscover"
        >
          <Loader2 v-if="discovering" class="mr-1 h-3.5 w-3.5 animate-spin" />
          <RefreshCw v-else class="mr-1 h-3.5 w-3.5" />
          Discover
        </Button>
      </div>
    </div>

    <p v-if="discoverError" class="pl-7 text-sm text-destructive">{{ discoverError }}</p>

    <ul v-if="expanded && visibleChildren.length > 0" class="ml-6 space-y-1 border-l pl-2">
      <DirectoryTreeNode
        v-for="child in visibleChildren"
        :key="child.id"
        :node="child"
      />
    </ul>
  </li>
</template>
