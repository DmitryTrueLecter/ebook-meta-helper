<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="min-h-screen bg-background text-foreground">
    <header class="border-b">
      <div class="container mx-auto flex items-center gap-6 px-4 py-3">
        <span class="text-lg font-semibold">Ebook Meta Helper</span>
        <nav class="flex items-center gap-4 text-sm">
          <RouterLink
            :to="{ name: 'directories' }"
            class="text-muted-foreground hover:text-foreground"
            active-class="text-foreground font-medium"
          >
            Directories
          </RouterLink>
          <RouterLink
            :to="{ name: 'scan' }"
            class="text-muted-foreground hover:text-foreground"
            active-class="text-foreground font-medium"
          >
            Scan
          </RouterLink>
        </nav>
      </div>
    </header>
    <main class="container mx-auto px-4 py-8">
      <RouterView />
    </main>
  </div>
</template>
