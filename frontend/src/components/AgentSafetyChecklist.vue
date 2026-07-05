<template>
  <DataPanel title="安全复核清单" subtitle="光伏逆变器现场作业前必须人工确认。">
    <div v-if="checklist" class="grid gap-3 lg:grid-cols-[240px_minmax(0,1fr)]">
      <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">风险等级</div>
        <div class="mt-3 text-2xl font-black" :class="riskClass">{{ riskLabel }}</div>
        <p class="mt-2 text-xs text-slate-400">机器生成清单仅用于辅助复核，不替代厂家手册。</p>
      </div>
      <div class="grid gap-3 md:grid-cols-3">
        <section class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
          <h3 class="font-black text-cyan-100">必须执行</h3>
          <ul class="mt-2 space-y-1 text-sm text-slate-200">
            <li v-for="item in mustDo" :key="item">- {{ item }}</li>
          </ul>
        </section>
        <section class="rounded-md border border-amber-300/20 bg-amber-400/10 p-3">
          <h3 class="font-black text-amber-100">风险警示</h3>
          <ul class="mt-2 space-y-1 text-sm text-slate-200">
            <li v-for="item in warnings" :key="item">- {{ item }}</li>
          </ul>
        </section>
        <section class="rounded-md border border-slate-500/20 bg-black/20 p-3">
          <h3 class="font-black text-white">记录要求</h3>
          <ul class="mt-2 space-y-1 text-sm text-slate-300">
            <li v-for="item in notices" :key="item">- {{ item }}</li>
          </ul>
        </section>
      </div>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">
      暂无安全清单，请先运行多模态证据智能体。
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'

const props = defineProps<{ checklist?: Record<string, unknown> | null }>()

const mustDo = computed(() => toTextList(props.checklist?.must_do))
const warnings = computed(() => toTextList(props.checklist?.warnings))
const notices = computed(() => toTextList(props.checklist?.notices))
const risk = computed(() => String(props.checklist?.risk_level || 'medium'))
const riskLabel = computed(() => risk.value === 'high' ? '高风险' : risk.value === 'low' ? '低风险' : '中风险')
const riskClass = computed(() => risk.value === 'high' ? 'text-red-100' : risk.value === 'low' ? 'text-emerald-100' : 'text-amber-100')

function toTextList(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : []
}
</script>
