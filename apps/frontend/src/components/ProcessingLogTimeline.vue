<script setup lang="ts">
import type { ProcessingLogEntry } from '@/types'

interface Props {
  entries: ProcessingLogEntry[]
}

defineProps<Props>()

// Map log level to a unicode glyph; unknown levels fall back to a neutral dot.
const LEVEL_ICON: Record<string, string> = {
  info: '✓',
  warning: '⚠',
  warn: '⚠',
  error: '✗',
  debug: '·',
}

const LEVEL_COLOR: Record<string, string> = {
  info: 'text-emerald-600 dark:text-emerald-400',
  warning: 'text-amber-600 dark:text-amber-400',
  warn: 'text-amber-600 dark:text-amber-400',
  error: 'text-red-600 dark:text-red-400',
  debug: 'text-muted-foreground',
}

function iconFor(level: string): string {
  return LEVEL_ICON[level] ?? '•'
}

function colorFor(level: string): string {
  return LEVEL_COLOR[level] ?? 'text-muted-foreground'
}

function formatTimestamp(iso: string): string {
  const parsed = new Date(iso)
  if (Number.isNaN(parsed.getTime())) {
    return iso
  }
  return parsed.toLocaleString()
}

function formatDuration(ms: number | null): string {
  if (ms === null) {
    return ''
  }
  if (ms < 1000) {
    return `${ms} ms`
  }
  return `${(ms / 1000).toFixed(2)} s`
}
</script>

<template>
  <ol class="space-y-2">
    <li
      v-for="(entry, index) in entries"
      :key="`${entry.created_at}-${entry.step}-${index}`"
      class="flex items-start gap-3 rounded-md border border-border bg-card px-3 py-2"
    >
      <span :class="['mt-0.5 text-base font-bold', colorFor(entry.level)]">
        {{ iconFor(entry.level) }}
      </span>
      <div class="flex-1 space-y-0.5">
        <div class="flex flex-wrap items-baseline gap-x-2 text-sm">
          <span class="font-mono text-xs text-muted-foreground">
            {{ formatTimestamp(entry.created_at) }}
          </span>
          <span class="font-semibold">{{ entry.step }}</span>
          <span v-if="entry.duration_ms !== null" class="text-xs text-muted-foreground">
            {{ formatDuration(entry.duration_ms) }}
          </span>
        </div>
        <p class="text-sm whitespace-pre-wrap break-words">{{ entry.message }}</p>
      </div>
    </li>
  </ol>
</template>
