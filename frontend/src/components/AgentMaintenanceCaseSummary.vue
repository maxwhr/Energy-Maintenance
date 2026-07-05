<template>
  <DataPanel v-if="summary" title="维修经验案例草稿" subtitle="从诊断、SOP、工单、媒体和工程师备注中沉淀出的案例摘要。">
    <div class="grid gap-3 lg:grid-cols-[260px_minmax(0,1fr)]">
      <section class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">案例标题</div>
        <h3 class="mt-2 text-lg font-black text-white">{{ text(summary.case_title) }}</h3>
        <p class="mt-2 text-sm text-slate-300">{{ text(summary.symptom) }}</p>
        <div class="mt-3 grid gap-2 text-xs text-slate-400">
          <span>厂家：{{ text(summary.manufacturer) }}</span>
          <span>系列：{{ text(summary.product_series) }}</span>
          <span>故障：{{ text(summary.fault_type) }}</span>
          <span>告警：{{ text(summary.alarm_code) }}</span>
        </div>
      </section>
      <section class="grid gap-3 md:grid-cols-2">
        <ListBlock title="可能原因" :items="rootCauseCandidates" />
        <ListBlock title="排查过程" :items="inspectionProcess" />
        <ListBlock title="安全注意" :items="safetyNotes" />
        <ListBlock title="限制说明" :items="limitations" />
      </section>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import ListBlock from '@/components/MultimodalListBlock.vue'

const props = defineProps<{ summary?: Record<string, unknown> | null }>()

const rootCauseCandidates = computed(() => toTextList(props.summary?.root_cause_candidates))
const inspectionProcess = computed(() => toTextList(props.summary?.inspection_process))
const safetyNotes = computed(() => toTextList(props.summary?.safety_notes))
const limitations = computed(() => toTextList(props.summary?.limitations))

function text(value: unknown) {
  return value == null || value === '' ? '-' : String(value)
}

function toTextList(value: unknown) {
  return Array.isArray(value)
    ? value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)).filter(Boolean)
    : []
}
</script>
