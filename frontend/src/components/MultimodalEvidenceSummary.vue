<template>
  <DataPanel title="多模态证据摘要" subtitle="机器识别只作为辅助证据，关键结论需要人工复核。">
    <div v-if="!summary" class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">
      请选择媒体后查看证据摘要。
    </div>
    <div v-else class="grid gap-3 md:grid-cols-4">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">处理任务</div>
        <div class="mt-1 text-2xl font-black text-white">{{ summary.jobs.length }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">OCR 结果</div>
        <div class="mt-1 text-2xl font-black text-white">{{ summary.ocr_results.length }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">AI 分析</div>
        <div class="mt-1 text-2xl font-black text-white">{{ summary.analyses.length }}</div>
      </div>
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">证据链接</div>
        <div class="mt-1 text-2xl font-black text-white">{{ summary.evidence_links.length }}</div>
      </div>
    </div>
    <p v-if="summary" class="mt-3 text-xs leading-5 text-amber-100">
      {{ summary.machine_result_boundary || '机器证据仅供检修参考，不等同最终诊断。' }}
    </p>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import type { MediaMultimodalSummary } from '@/types/multimodal'

defineProps<{
  summary: MediaMultimodalSummary | null
}>()
</script>
