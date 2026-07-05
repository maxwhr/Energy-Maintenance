<template>
  <DataPanel title="AI 多模态分析" subtitle="分析结果仅供参考，不能替代厂家手册和现场安全确认。">
    <div v-if="analyses.length" class="space-y-3">
      <article v-for="item in analyses" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-black text-white">{{ item.analysis_type || 'general' }}</span>
              <MultimodalStatusPill :value="item.human_review_status" />
              <MultimodalStatusPill v-if="isMocked(item.raw_response_json)" value="mocked" />
            </div>
            <p class="mt-1 text-xs text-slate-400">
              provider={{ item.provider_code }} / 置信度={{ formatConfidence(item.confidence) }} / trace={{ item.external_trace_id || '-' }}
            </p>
          </div>
          <div v-if="canReview" class="flex flex-wrap gap-2">
            <button class="scada-button !min-h-8 !px-3" type="button" @click="$emit('review', item.id, 'accepted')">确认</button>
            <button class="scada-button !min-h-8 !px-3" type="button" @click="$emit('review', item.id, 'rejected')">驳回</button>
            <button class="scada-button !min-h-8 !px-3" type="button" @click="$emit('review', item.id, 'revised')">标记修订</button>
          </div>
        </div>
        <p class="mt-3 rounded-md bg-black/30 p-3 text-sm leading-6 text-slate-100">{{ item.summary || '暂无分析摘要' }}</p>
        <div class="mt-3 grid gap-3 md:grid-cols-2">
          <MultimodalListBlock title="可见文字" :items="textList(item.detected_text)" />
          <MultimodalListBlock title="告警代码" :items="arrayList(item.detected_alarm_codes_json)" />
          <MultimodalListBlock title="视觉发现" :items="objectList(item.visual_findings_json, 'finding')" />
          <MultimodalListBlock title="故障线索" :items="objectList(item.possible_faults_json, 'reason')" />
          <MultimodalListBlock title="安全风险" :items="objectList(item.safety_risks_json, 'risk')" />
          <MultimodalListBlock title="建议步骤" :items="objectList(item.recommended_actions_json, 'action')" />
        </div>
        <details class="mt-2">
          <summary class="cursor-pointer text-xs font-bold text-cyan-200">技术结果 JSON</summary>
          <pre class="mt-2 max-h-56 overflow-auto rounded bg-black/40 p-3 text-xs text-slate-300">{{ pretty(item.raw_response_json || {}) }}</pre>
        </details>
      </article>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">暂无 AI 分析结果。</div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalListBlock from '@/components/MultimodalListBlock.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { MediaAIAnalysis } from '@/types/multimodal'

defineProps<{
  analyses: MediaAIAnalysis[]
  canReview?: boolean
}>()

defineEmits<{
  review: [id: string, status: 'accepted' | 'rejected' | 'revised']
}>()

function isMocked(value?: Record<string, unknown> | null) {
  return value?.mocked === true || (value?.normalized_result as Record<string, unknown> | undefined)?.mocked === true
}

function formatConfidence(value?: number | string | null) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${Math.round(parsed * 100)}%` : '-'
}

function textList(value?: string | null) {
  return value ? value.split(/\n+/).filter(Boolean) : []
}

function arrayList(value?: unknown[] | null) {
  return (value || []).map((item) => String(item))
}

function objectList(value?: Record<string, unknown> | unknown[] | null, key = 'text') {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (item && typeof item === 'object') return String((item as Record<string, unknown>)[key] || JSON.stringify(item))
    return String(item)
  })
}

function pretty(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
