<template>
  <DataPanel title="人工复核边界" subtitle="高风险作业建议必须由具备权限的人员审批。">
    <div class="grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">审批状态</div>
        <div class="mt-1 font-black text-white">{{ approvalStatus || 'not_required' }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">草稿产物</div>
        <div class="mt-1 font-black text-white">{{ artifactCount }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">正式写入</div>
        <div class="mt-1 font-black text-amber-100">未自动执行</div>
      </div>
    </div>
    <p class="mt-3 text-sm text-slate-300">
      诊断、SOP 和工单智能体只提供结构化草稿和可追溯依据；审批通过仅更新 Agent 审批状态，不会自动创建正式工单或执行 SOP。
    </p>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'

defineProps<{ approvalStatus?: string | null; artifactCount: number }>()
</script>
