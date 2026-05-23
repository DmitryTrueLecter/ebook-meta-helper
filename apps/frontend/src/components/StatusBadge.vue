<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from '@/components/ui/badge'
import type { FileStatus } from '@/types'

interface Props {
  status: FileStatus
}

const props = defineProps<Props>()

// ai_queued has no explicit color in the spec — grouped with reading/enriching as in-flight.
const STATUS_STYLES: Record<FileStatus, string> = {
  pending: 'bg-gray-200 text-gray-800 border-transparent',
  reading: 'bg-blue-100 text-blue-800 border-transparent animate-pulse',
  ai_queued: 'bg-blue-100 text-blue-800 border-transparent animate-pulse',
  enriching: 'bg-blue-100 text-blue-800 border-transparent animate-pulse',
  enriched: 'bg-yellow-100 text-yellow-800 border-transparent',
  accepted: 'bg-green-100 text-green-800 border-transparent',
  rejected: 'bg-gray-200 text-gray-600 border-transparent line-through',
  failed: 'bg-red-100 text-red-800 border-transparent',
}

const STATUS_LABELS: Record<FileStatus, string> = {
  pending: 'pending',
  reading: 'reading',
  ai_queued: 'AI queued',
  enriching: 'enriching',
  enriched: 'enriched',
  accepted: 'accepted',
  rejected: 'rejected',
  failed: 'failed',
}

const badgeClass = computed(() => STATUS_STYLES[props.status])
const label = computed(() => STATUS_LABELS[props.status])
</script>

<template>
  <Badge variant="outline" :class="badgeClass">{{ label }}</Badge>
</template>
