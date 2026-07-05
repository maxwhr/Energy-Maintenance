<template>
  <DataPanel v-if="summary" title="故障诊断摘要" subtitle="诊断建议仅供作业辅助，正式处理前必须人工复核。">
    <div class="grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">厂家 / 系列</div>
        <div class="mt-1 font-black text-white">{{ text(summary.manufacturer) }} / {{ text(summary.product_series) }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">故障类型</div>
        <div class="mt-1 font-black text-white">{{ text(summary.fault_type) }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">告警代码</div>
        <div class="mt-1 font-black text-white">{{ text(summary.alarm_code) }}</div>
      </div>
    </div>

    <p class="mt-3 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3 text-sm text-cyan-50">
      {{ text(summary.symptom_summary) }}
    </p>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <ListBlock title="可能原因" :items="arrayOfText(summary.possible_causes)" />
      <ListBlock title="排查步骤" :items="arrayOfText(summary.inspection_steps)" />
      <ListBlock title="推荐处理" :items="arrayOfText(summary.recommended_actions)" />
      <ListBlock title="安全风险" :items="arrayOfText(summary.safety_risks)" />
    </div>

    <div class="mt-4 grid gap-3 md:grid-cols-2">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">知识引用</div>
        <div class="mt-1 text-2xl font-black text-white">{{ list(summary.knowledge_references).length }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">置信度</div>
        <div class="mt-1 text-2xl font-black text-white">{{ percent(summary.confidence) }}</div>
      </div>
    </div>

    <ListBlock class="mt-4" title="边界说明" :items="arrayOfText(summary.limitations)" />
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import ListBlock from '@/components/MultimodalListBlock.vue'

defineProps<{ summary: Record<string, unknown> | null }>()

function text(value: unknown) {
  return typeof value === 'string' && value ? value : '-'
}

function list(value: unknown) {
  return Array.isArray(value) ? value : []
}

function arrayOfText(value: unknown) {
  return list(value).map((item) => (typeof item === 'string' ? item : JSON.stringify(item))).filter(Boolean)
}

function percent(value: unknown) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return '-'
  return `${Math.round(numberValue * 100)}%`
}
</script>
