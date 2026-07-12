<template>
  <div class="empty-state rounded-lg border border-dashed border-slate-600/20 bg-black/10 px-5 py-8 text-center">
    <div class="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-cyan-400/10 text-cyan-200">
      <Inbox :size="19" />
    </div>
    <div class="text-sm font-bold text-slate-300">{{ title || '暂无数据' }}</div>
    <p class="mx-auto mt-1 max-w-xl text-xs leading-5 text-slate-400">{{ text }}</p>
    <div v-if="$slots.default" class="mt-4"><slot /></div>
  </div>
</template>

<script setup lang="ts">
import { Inbox } from '@lucide/vue'

defineProps<{
  text: string
  title?: string
}>()
</script>
