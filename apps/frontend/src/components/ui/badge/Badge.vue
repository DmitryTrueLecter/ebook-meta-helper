<script setup lang="ts">
import { type BadgeVariants, badgeVariants } from '.'
import { cn } from '@/lib/utils'

interface Props {
  variant?: BadgeVariants['variant']
  class?: string
}

const props = defineProps<Props>()
</script>

<template>
  <div :class="cn(badgeVariants({ variant: props.variant }), props.class)">
    <slot />
  </div>
</template>
