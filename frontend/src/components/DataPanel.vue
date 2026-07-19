<template>
  <section class="scada-panel overflow-hidden rounded-lg">
    <header v-if="title || $slots.actions" class="flex min-h-14 items-center justify-between gap-4 border-b border-slate-600/20 px-5 py-3">
      <div>
        <h2 v-if="title" class="text-sm font-black text-slate-50">{{ title }}</h2>
        <p v-if="subtitle" class="mt-1 text-xs leading-5 text-slate-400">{{ subtitle }}</p>
      </div>
      <slot name="actions" />
    </header>
    <div class="p-4 sm:p-5">
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
