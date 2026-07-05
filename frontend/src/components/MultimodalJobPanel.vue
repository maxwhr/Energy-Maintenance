<template>
  <DataPanel title="处理任务" subtitle="dry-run 只构造请求，不调用外部 API；mock-run 是本地联调结果。">
    <template #actions>
      <div class="flex flex-wrap gap-2">
        <button class="scada-button !min-h-8 !px-3" type="button" :disabled="!mediaId || busy || readonly" @click="$emit('create-ocr-dry-run')">
          OCR dry-run
        </button>
        <button class="scada-button !min-h-8 !px-3" type="button" :disabled="!mediaId || busy || readonly" @click="$emit('create-ai-dry-run')">
          AI dry-run
        </button>
        <button class="scada-button primary !min-h-8 !px-3" type="button" :disabled="!mediaId || busy || !canMock" @click="$emit('create-ai-mock-run')">
          AI mock-run
        </button>
        <button class="scada-button primary !min-h-8 !px-3" type="button" :disabled="!mediaId || busy || !canMock" @click="$emit('create-ocr-mock-run')">
          OCR mock-run
        </button>
      </div>
    </template>

    <div v-if="!mediaId" class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">请选择媒体。</div>
    <div v-else-if="jobs.length" class="space-y-3">
      <article v-for="job in jobs" :key="job.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="font-black text-white">{{ formatJobType(job.job_type) }}</span>
              <MultimodalStatusPill :value="job.status" />
            </div>
            <p class="mt-1 text-xs text-slate-400">
              provider={{ job.provider_code }} / progress={{ job.progress }}% / trace={{ job.external_trace_id || '-' }}
            </p>
            <p v-if="job.error_code || job.error_message" class="mt-1 text-xs text-amber-100">
              {{ job.error_code || '' }} {{ job.error_message || '' }}
            </p>
          </div>
          <div class="text-xs text-slate-500">{{ formatTime(job.created_at) }}</div>
        </div>
        <details class="mt-2">
          <summary class="cursor-pointer text-xs font-bold text-cyan-200">技术摘要 JSON</summary>
          <pre class="mt-2 max-h-52 overflow-auto rounded bg-black/40 p-3 text-xs text-slate-300">{{ pretty(job.result_summary_json || job.request_summary_json || {}) }}</pre>
        </details>
      </article>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">暂无处理任务。</div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { MediaProcessingJob } from '@/types/multimodal'

defineProps<{
  mediaId?: string | null
  jobs: MediaProcessingJob[]
  busy?: boolean
  readonly?: boolean
  canMock?: boolean
}>()

defineEmits<{
  'create-ocr-dry-run': []
  'create-ai-dry-run': []
  'create-ai-mock-run': []
  'create-ocr-mock-run': []
}>()

function formatJobType(value: string) {
  const labels: Record<string, string> = {
    ocr: 'OCR 处理',
    multimodal_analysis: '多模态分析',
    combined: '组合处理',
    manual_review: '人工复核'
  }
  return labels[value] || value
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function pretty(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
