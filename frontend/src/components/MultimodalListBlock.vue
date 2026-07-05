<template>
  <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
    <div class="text-xs font-bold text-slate-400">{{ title }}</div>
    <ul v-if="items.length" class="mt-2 space-y-1 text-sm text-slate-200">
      <li v-for="(item, index) in items" :key="index">- {{ item }}</li>
    </ul>
    <div v-else class="mt-2 text-xs text-slate-500">暂无</div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  items: string[]
}>()
</script>
