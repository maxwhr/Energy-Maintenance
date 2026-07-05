<template>
  <DataPanel title="智能体执行时间线" subtitle="展示 validate、OCR、视觉分析、安全复核、证据链和 finalize 等编排步骤。">
    <div v-if="steps.length" class="space-y-3">
      <article v-for="step in steps" :key="step.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="font-mono text-xs text-slate-400">#{{ step.step_index }}</span>
          <span class="font-black text-white">{{ step.step_name }}</span>
          <MultimodalStatusPill :value="step.status" />
        </div>
        <p v-if="step.reasoning_summary" class="mt-2 text-sm text-slate-300">{{ step.reasoning_summary }}</p>
        <p v-if="step.error_message" class="mt-2 text-xs text-amber-100">{{ step.error_message }}</p>
      </article>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">暂无步骤。</div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { AgentStep } from '@/types/agent'

defineProps<{ steps: AgentStep[] }>()
</script>
