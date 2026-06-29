<template>
  <section class="scada-panel rounded-md">
    <header v-if="title || $slots.actions" class="flex min-h-12 items-center justify-between border-b border-slate-600/20 px-4">
      <div>
        <h2 v-if="title" class="text-sm font-black text-slate-50">{{ title }}</h2>
        <p v-if="subtitle" class="text-xs text-slate-400">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div class="p-4">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  subtitle?: string
}>()
</script>
