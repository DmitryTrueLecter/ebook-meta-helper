<script setup lang="ts">
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { DiffRow } from '@/composables/useMetadataDiff'

interface Props {
  title: string
  rows: DiffRow[]
  side: 'file' | 'ai'
  isEmpty?: boolean
  emptyMessage?: string
}

const props = withDefaults(defineProps<Props>(), {
  isEmpty: false,
  emptyMessage: '',
})

// Highlight cue is one-sided per the issue's Layout section — file side renders neutrally.
const HIGHLIGHT_CLASS: Record<DiffRow['highlight'], string> = {
  none: '',
  changed: 'bg-yellow-100 dark:bg-yellow-900/30',
  new: 'bg-green-100 dark:bg-green-900/30',
}

function classFor(row: DiffRow): string {
  if (props.side === 'file') {
    return ''
  }
  return HIGHLIGHT_CLASS[row.highlight]
}

function valueFor(row: DiffRow): string {
  return props.side === 'file' ? row.fileValue : row.aiValue
}
</script>

<template>
  <Card class="h-full">
    <CardHeader>
      <CardTitle>{{ title }}</CardTitle>
    </CardHeader>
    <CardContent>
      <p v-if="isEmpty" class="text-sm text-muted-foreground">{{ emptyMessage }}</p>
      <dl v-else class="space-y-2">
        <div
          v-for="row in rows"
          :key="row.key"
          :class="['rounded-md px-2 py-1', classFor(row)]"
        >
          <dt class="text-xs font-medium uppercase text-muted-foreground">{{ row.label }}</dt>
          <dd class="text-sm whitespace-pre-wrap break-words">
            {{ valueFor(row) || '—' }}
          </dd>
        </div>
      </dl>
    </CardContent>
  </Card>
</template>
