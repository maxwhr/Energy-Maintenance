<template>
  <DataPanel v-if="draft" title="工单草稿" subtitle="草稿仅供审批与人工转单参考，不会自动创建正式检修工单。">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-black text-white">{{ text(draft.title) }}</h3>
        <p class="mt-1 text-sm text-slate-400">{{ text(draft.manufacturer) }} / {{ text(draft.product_series) }} / {{ text(draft.fault_type) }}</p>
      </div>
      <span class="rounded border border-amber-300/30 bg-amber-400/10 px-3 py-1 text-xs font-bold text-amber-100">不自动创建正式工单</span>
    </div>

    <p class="mt-4 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-200">
      {{ text(draft.description) }}
    </p>

    <div class="mt-4 grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">优先级</div>
        <div class="mt-1 font-black text-white">{{ text(draft.priority) }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">建议负责人</div>
        <div class="mt-1 font-black text-white">{{ text(draft.suggested_assignee_id) }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">建议截止</div>
        <div class="mt-1 font-black text-white">{{ text(draft.suggested_due_time) }}</div>
      </div>
    </div>

    <ListBlock class="mt-4" title="安全要求" :items="arrayOfText(draft.safety_notes)" />

    <div class="mt-4 grid gap-3 md:grid-cols-2">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
        <div class="text-xs font-bold text-slate-400">来源 Agent Run</div>
        <div class="mt-1 break-all font-mono text-xs text-cyan-100">{{ text(draft.source_agent_run_id) }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
        <div class="text-xs font-bold text-slate-400">正式工单状态</div>
        <div class="mt-1 font-bold text-amber-100">{{ draft.formal_task_created ? '已创建' : '未创建' }}</div>
      </div>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import ListBlock from '@/components/MultimodalListBlock.vue'

defineProps<{ draft: Record<string, unknown> | null }>()

function text(value: unknown) {
  return typeof value === 'string' && value ? value : '-'
}

function arrayOfText(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.map((item) => (typeof item === 'string' ? item : JSON.stringify(item))).filter(Boolean)
}
</script>
