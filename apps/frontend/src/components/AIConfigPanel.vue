<script setup lang="ts">
import { computed } from 'vue'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { AIConfigVersionView } from '@/types'

interface Props {
  config: AIConfigVersionView
}

const props = defineProps<Props>()

const versionLabel = computed(() => {
  const suffix = props.config.label ? ` · ${props.config.label}` : ''
  return `v${props.config.version}${suffix}`
})
</script>

<template>
  <Card>
    <CardHeader>
      <CardTitle class="flex flex-wrap items-center gap-2 text-base">
        <span>Active AI configuration</span>
        <span
          data-testid="config-version"
          class="rounded bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground"
        >
          {{ versionLabel }}
        </span>
      </CardTitle>
    </CardHeader>
    <CardContent class="space-y-4">
      <dl class="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-3">
        <div>
          <dt class="text-xs uppercase text-muted-foreground">cheap model</dt>
          <dd class="font-medium">{{ props.config.cheap_model }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-muted-foreground">expensive model</dt>
          <dd class="font-medium">{{ props.config.expensive_model }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-muted-foreground">effort</dt>
          <dd class="font-medium">{{ props.config.effort }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-muted-foreground">escalation threshold</dt>
          <dd class="font-medium">{{ props.config.escalation_threshold }}</dd>
        </div>
        <div>
          <dt class="text-xs uppercase text-muted-foreground">provider</dt>
          <dd class="font-medium">{{ props.config.provider }}</dd>
        </div>
      </dl>

      <details data-testid="config-system-prompt">
        <summary class="cursor-pointer text-sm font-semibold">System prompt</summary>
        <pre
          class="mt-2 max-h-64 overflow-auto rounded-md border border-border bg-muted/40 p-3 text-xs whitespace-pre-wrap break-words"
        >{{ props.config.system_prompt }}</pre>
      </details>
    </CardContent>
  </Card>
</template>
