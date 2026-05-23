<script setup lang="ts">
import { computed } from 'vue'

import { Badge } from '@/components/ui/badge'
import type { BadgeVariants } from '@/components/ui/badge'
import type { FileStatus } from '@/types'

interface Props {
  status: FileStatus
}

const props = defineProps<Props>()

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

// In-flight states pulse to signal background activity.
const PULSING_STATUSES: ReadonlySet<FileStatus> = new Set(['reading', 'ai_queued', 'enriching'])

const variant = computed(() => STATUS_VARIANT[props.status])
const isPulsing = computed(() => PULSING_STATUSES.has(props.status))
</script>

<template>
  <Badge :variant="variant" :class="isPulsing ? 'animate-pulse' : ''">
    {{ status }}
  </Badge>
</template>
