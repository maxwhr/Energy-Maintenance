<template>
  <span class="inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-bold" :class="classes">
    <span class="status-dot"></span>
    {{ displayLabel }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatStatusLabel } from '@/utils/display'

const props = defineProps<{
  value?: string
  label?: string
}>()

const tone = computed(() => props.value ?? 'online')
const displayLabel = computed(() => props.label ?? formatStatusLabel(tone.value))

const classes = computed(() => {
  if (['fault', 'failed', 'error', 'high', 'critical', 'urgent', 'rejected'].includes(tone.value)) {
    return 'border-red-400/30 bg-red-500/10 text-red-300'
  }
  if (
    ['warning', 'processing', 'medium', 'maintenance', 'parsing', 'pending', 'assigned', 'in_progress', 'draft', 'submitted', 'changes_requested'].includes(tone.value)
  ) {
    return 'border-amber-300/30 bg-amber-400/10 text-amber-200'
  }
  if (['offline', 'canceled', 'cancelled', 'low', 'inactive', 'retired', 'archived'].includes(tone.value)) {
    return 'border-slate-400/30 bg-slate-500/10 text-slate-300'
  }
  return 'border-emerald-300/30 bg-emerald-400/10 text-emerald-200'
})
</script>
