<script setup lang="ts">
import type { AICallSummary, AICallTier } from '@/types'

interface Props {
  calls: AICallSummary[]
  selectedId?: number | null
}

const props = withDefaults(defineProps<Props>(), {
  selectedId: null,
})

const emit = defineEmits<{ select: [callId: number] }>()

const TIER_STYLES: Record<AICallTier, string> = {
  cheap: 'bg-sky-100 text-sky-800 dark:bg-sky-900/40 dark:text-sky-200',
  expensive: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200',
}

function tierClass(tier: AICallTier): string {
  return TIER_STYLES[tier]
}

function formatConfidence(value: number | null): string {
  return value === null ? '—' : `${(value * 100).toFixed(0)}%`
}

function formatTokens(prompt: number | null, completion: number | null): string {
  if (prompt === null && completion === null) {
    return '—'
  }
  return `${prompt ?? 0} / ${completion ?? 0}`
}

function formatCost(value: number | null): string {
  return value === null ? '—' : `$${value.toFixed(4)}`
}

function formatDuration(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(2)} s`
}
</script>

<template>
  <ol class="space-y-2">
    <li
      v-for="call in props.calls"
      :key="call.id"
      :data-testid="`ai-call-${call.id}`"
      :class="[
        'cursor-pointer rounded-md border px-3 py-2 transition-colors',
        call.id === props.selectedId
          ? 'border-primary ring-1 ring-primary'
          : 'border-border hover:bg-muted/50',
      ]"
      @click="emit('select', call.id)"
    >
      <div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span class="font-mono text-xs text-muted-foreground">#{{ call.sequence }}</span>
        <span :class="['rounded px-1.5 py-0.5 text-xs font-semibold', tierClass(call.tier)]">
          {{ call.tier }}
        </span>
        <span class="font-medium">{{ call.model }}</span>
        <span
          v-if="call.is_canonical"
          data-testid="canonical-marker"
          class="rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-semibold text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
        >
          ★ canonical
        </span>
      </div>
      <dl class="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-muted-foreground sm:grid-cols-4">
        <div>
          <dt class="uppercase">confidence</dt>
          <dd class="text-foreground">{{ formatConfidence(call.confidence) }}</dd>
        </div>
        <div>
          <dt class="uppercase">tokens (p/c)</dt>
          <dd class="text-foreground">
            {{ formatTokens(call.prompt_tokens, call.completion_tokens) }}
          </dd>
        </div>
        <div>
          <dt class="uppercase">cost</dt>
          <dd class="text-foreground">{{ formatCost(call.cost_usd) }}</dd>
        </div>
        <div>
          <dt class="uppercase">duration</dt>
          <dd class="text-foreground">{{ formatDuration(call.duration_ms) }}</dd>
        </div>
      </dl>
    </li>
  </ol>
</template>
