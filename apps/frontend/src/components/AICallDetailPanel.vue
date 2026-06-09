<script setup lang="ts">
import { computed } from 'vue'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AICallDetail, JsonValue } from '@/types'

interface Props {
  call: AICallDetail
}

const props = defineProps<Props>()

const parseErrorsText = computed<string | null>(() => formatParseErrors(props.call.parse_errors))

// parse_errors is free-form JSON; strings render verbatim, structured payloads are pretty-printed.
function formatParseErrors(errors: JsonValue | null): string | null {
  if (errors === null || errors === undefined) {
    return null
  }
  if (typeof errors === 'string') {
    return errors === '' ? null : errors
  }
  return JSON.stringify(errors, null, 2)
}
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="flex flex-wrap items-center gap-2 text-base">
        <span>Call #{{ props.call.sequence }} detail</span>
        <span class="text-xs font-normal text-muted-foreground">{{ props.call.model }}</span>
      </CardTitle>
    </CardHeader>
    <CardContent class="space-y-4">
      <details open data-testid="system-prompt-block">
        <summary class="cursor-pointer text-sm font-semibold">System prompt</summary>
        <pre
          class="mt-2 max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs whitespace-pre-wrap break-words"
        >{{ props.call.system_prompt }}</pre>
      </details>

      <details open data-testid="user-prompt-block">
        <summary class="cursor-pointer text-sm font-semibold">User prompt</summary>
        <pre
          class="mt-2 max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs whitespace-pre-wrap break-words"
        >{{ props.call.user_prompt }}</pre>
      </details>

      <details open data-testid="raw-response-block">
        <summary class="cursor-pointer text-sm font-semibold">Raw response (pre-parse)</summary>
        <pre
          class="mt-2 max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs whitespace-pre-wrap break-words"
        >{{ props.call.raw_response }}</pre>
      </details>

      <details v-if="parseErrorsText !== null" open data-testid="parse-errors-block">
        <summary class="cursor-pointer text-sm font-semibold text-destructive">Parse errors</summary>
        <pre
          class="mt-2 max-h-64 overflow-auto rounded-md border border-destructive/40 bg-destructive/10 p-3 text-xs whitespace-pre-wrap break-words"
        >{{ parseErrorsText }}</pre>
      </details>
      <p v-else class="text-xs text-muted-foreground">No parse errors recorded for this call.</p>
    </CardContent>
  </Card>
</template>
