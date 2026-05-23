<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const rawId = Array.isArray(route.params.id) ? route.params.id[0] : route.params.id
</script>

<template>
  <section class="space-y-2">
    <h1 class="text-2xl font-bold tracking-tight">File detail</h1>
    <p class="text-muted-foreground">File #{{ rawId }} — detail view lands in a follow-up task.</p>
  </section>
</template>
