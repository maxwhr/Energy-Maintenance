<template>
  <DataPanel title="OCR 结果" subtitle="OCR 文字仅作为检修证据摘录，需要人工核对原图。">
    <div v-if="results.length" class="space-y-3">
      <article v-for="item in results" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <div class="flex flex-wrap items-center gap-2">
            <span class="font-black text-white">{{ item.provider_code }}</span>
            <MultimodalStatusPill :value="item.status || 'succeeded'" />
            <MultimodalStatusPill v-if="isMocked(item.raw_result_json)" value="mocked" />
          </div>
          <span class="text-xs text-slate-500">{{ formatTime(item.created_at) }}</span>
        </div>
        <div class="mt-2 grid gap-2 text-xs text-slate-300 md:grid-cols-3">
          <span>语言：{{ item.language || '-' }}</span>
          <span>置信度：{{ formatConfidence(item.confidence) }}</span>
          <span>trace：{{ item.external_trace_id || '-' }}</span>
        </div>
        <p class="mt-3 whitespace-pre-wrap rounded-md bg-black/30 p-3 text-sm leading-6 text-slate-100">{{ item.text || '暂无 OCR 文本' }}</p>
        <details class="mt-2">
          <summary class="cursor-pointer text-xs font-bold text-cyan-200">技术结果 JSON</summary>
          <pre class="mt-2 max-h-56 overflow-auto rounded bg-black/40 p-3 text-xs text-slate-300">{{ pretty(item.raw_result_json || {}) }}</pre>
        </details>
      </article>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">暂无 OCR 结果。</div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { MediaOCRResult } from '@/types/multimodal'

defineProps<{
  results: MediaOCRResult[]
}>()

function isMocked(value?: Record<string, unknown> | null) {
  return value?.mocked === true || (value?.normalized_result as Record<string, unknown> | undefined)?.mocked === true
}

function formatConfidence(value?: number | string | null) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${Math.round(parsed * 100)}%` : '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function pretty(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
