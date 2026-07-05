<template>
  <span class="inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-bold" :class="classes">
    <span class="status-dot"></span>
    {{ label || formatMultimodalStatus(value) }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  value?: string | null
  label?: string
}>()

const tone = computed(() => props.value || 'not_configured')

const classes = computed(() => {
  if (['failed', 'error', 'rejected'].includes(tone.value)) return 'border-red-400/30 bg-red-500/10 text-red-300'
  if (['blocked', 'not_configured', 'disabled', 'pending', 'running', 'would_call'].includes(tone.value)) {
    return 'border-amber-300/30 bg-amber-400/10 text-amber-200'
  }
  if (['mocked', 'revised'].includes(tone.value)) return 'border-violet-300/30 bg-violet-400/10 text-violet-200'
  if (['cancelled', 'archived'].includes(tone.value)) return 'border-slate-400/30 bg-slate-500/10 text-slate-300'
  return 'border-emerald-300/30 bg-emerald-400/10 text-emerald-200'
})

function formatMultimodalStatus(value?: string | null) {
  const labels: Record<string, string> = {
    blocked: '已阻断',
    not_configured: '未配置',
    disabled: '未启用',
    would_call: '可调用预检',
    mocked: '模拟结果',
    succeeded: '成功',
    success: '成功',
    failed: '失败',
    pending: '待处理',
    running: '运行中',
    cancelled: '已取消',
    accepted: '已确认',
    rejected: '已驳回',
    revised: '已修订',
    available: '可用',
    unavailable: '不可用'
  }
  return labels[value || ''] || value || '-'
}
</script>
