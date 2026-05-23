<script setup lang="ts">
import { computed } from 'vue'

import { Badge } from '@/components/ui/badge'
import type { BadgeVariants } from '@/components/ui/badge'
import type { FileStatus } from '@/types'

interface Props {
  status: FileStatus
}

const props = defineProps<Props>()

// Stable status → badge variant mapping. Statuses not listed fall back to `outline`.
const STATUS_VARIANT: Record<FileStatus, BadgeVariants['variant']> = {
  pending: 'secondary',
  reading: 'secondary',
  ai_queued: 'secondary',
  enriching: 'secondary',
  enriched: 'default',
  accepted: 'default',
  rejected: 'destructive',
  failed: 'destructive',
}

// `enriching` and `ai_queued` are in-flight states — pulse to signal activity.
const PULSING_STATUSES: ReadonlySet<FileStatus> = new Set(['ai_queued', 'enriching', 'reading'])

const variant = computed(() => STATUS_VARIANT[props.status])
const isPulsing = computed(() => PULSING_STATUSES.has(props.status))
</script>

<template>
  <Badge :variant="variant" :class="isPulsing ? 'animate-pulse' : ''">
    {{ status }}
  </Badge>
</template>
