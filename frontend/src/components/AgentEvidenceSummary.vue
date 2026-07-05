<template>
  <DataPanel title="智能体证据摘要" subtitle="汇总 OCR、视觉分析、blocked/mock 状态和人工复核边界。">
    <div v-if="summary" class="grid gap-3 lg:grid-cols-2">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">执行边界</div>
        <div class="mt-2 flex flex-wrap gap-2">
          <MultimodalStatusPill :value="String(summary.ocr_status || 'not_checked')" />
          <MultimodalStatusPill :value="String(summary.visual_analysis_status || 'not_checked')" />
          <span v-if="summary.mocked" class="rounded bg-amber-400/15 px-2 py-1 text-xs font-bold text-amber-100">mocked</span>
          <span v-if="summary.dry_run" class="rounded bg-cyan-400/15 px-2 py-1 text-xs font-bold text-cyan-100">dry-run</span>
        </div>
        <p class="mt-3 text-sm text-slate-300">
          {{ summary.external_api_called ? '存在外部 API 调用记录' : '未调用真实外部 API' }}，机器证据需人工复核。
        </p>
      </div>

      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">媒体与类型</div>
        <p class="mt-2 font-mono text-xs text-slate-300">{{ mediaText }}</p>
        <p class="mt-2 text-sm text-slate-300">{{ summary.image_type || '光伏逆变器现场图片' }}</p>
      </div>

      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">可见文本 / 告警代码</div>
        <ul class="mt-2 space-y-1 text-sm text-slate-300">
          <li v-for="item in visibleText" :key="item">{{ item }}</li>
          <li v-if="!visibleText.length" class="text-slate-500">暂无 OCR 可见文本。</li>
        </ul>
        <div class="mt-2 flex flex-wrap gap-2">
          <span v-for="item in alarmCodes" :key="item" class="rounded bg-red-400/15 px-2 py-1 text-xs font-bold text-red-100">{{ item }}</span>
        </div>
      </div>

      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">建议下一步</div>
        <ul class="mt-2 space-y-1 text-sm text-slate-300">
          <li v-for="item in nextSteps" :key="item">- {{ item }}</li>
          <li v-if="!nextSteps.length" class="text-slate-500">暂无建议。</li>
        </ul>
      </div>

      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3 lg:col-span-2">
        <div class="text-xs font-bold text-slate-400">限制说明</div>
        <ul class="mt-2 space-y-1 text-sm text-slate-300">
          <li v-for="item in limitations" :key="item">- {{ item }}</li>
        </ul>
      </div>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">
      暂无多模态证据摘要，请先创建智能体运行。
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'

const props = defineProps<{ summary?: Record<string, unknown> | null }>()

const mediaText = computed(() => ((props.summary?.media_ids as string[] | undefined) || []).join(', ') || '-')
const visibleText = computed(() => toTextList(props.summary?.visible_text))
const alarmCodes = computed(() => toTextList(props.summary?.detected_alarm_codes))
const nextSteps = computed(() => toTextList(props.summary?.recommended_next_steps))
const limitations = computed(() => toTextList(props.summary?.limitations))

function toTextList(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.map((item) => {
    if (typeof item === 'string') return item
    if (item && typeof item === 'object') {
      const record = item as Record<string, unknown>
      return String(record.action || record.finding || record.risk || record.fault_type || JSON.stringify(record))
    }
    return String(item)
  }).filter(Boolean)
}
</script>
