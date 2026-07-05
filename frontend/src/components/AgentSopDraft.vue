<template>
  <DataPanel v-if="draft" title="SOP 草稿" subtitle="草稿不会自动转为正式 SOP execution，需 expert/admin 审批。">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-lg font-black text-white">{{ text(draft.title) }}</h3>
        <p class="mt-1 text-sm text-slate-400">{{ text(draft.manufacturer) }} / {{ text(draft.product_series) }} / {{ text(draft.fault_type) }}</p>
      </div>
      <span class="rounded border border-amber-300/30 bg-amber-400/10 px-3 py-1 text-xs font-bold text-amber-100">需要人工审批</span>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <ListBlock title="前置条件" :items="arrayOfText(draft.preconditions)" />
      <ListBlock title="安全要求" :items="arrayOfText(draft.safety_requirements)" />
      <ListBlock title="工具" :items="arrayOfText(draft.tools)" />
      <ListBlock title="材料" :items="arrayOfText(draft.materials)" />
    </div>

    <div class="mt-4 rounded-md border border-slate-600/20 bg-black/20 p-3">
      <div class="text-xs font-bold text-slate-400">作业步骤</div>
      <ol v-if="steps.length" class="mt-2 space-y-2 text-sm text-slate-200">
        <li v-for="(item, index) in steps" :key="index" class="rounded bg-black/20 p-2">
          <span class="font-mono text-xs text-cyan-200">#{{ index + 1 }}</span>
          {{ item }}
        </li>
      </ol>
      <div v-else class="mt-2 text-xs text-slate-500">暂无步骤。</div>
    </div>

    <div class="mt-4 grid gap-4 lg:grid-cols-2">
      <ListBlock title="验收标准" :items="arrayOfText(draft.acceptance_criteria)" />
      <ListBlock title="复核要点" :items="arrayOfText(draft.review_points)" />
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import ListBlock from '@/components/MultimodalListBlock.vue'

const props = defineProps<{ draft: Record<string, unknown> | null }>()

const steps = computed(() => arrayOfText(props.draft?.steps))

function text(value: unknown) {
  return typeof value === 'string' && value ? value : '-'
}

function arrayOfText(value: unknown) {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => {
      if (typeof item === 'string') return item
      if (item && typeof item === 'object') {
        const record = item as Record<string, unknown>
        return String(record.title || record.name || record.action || record.description || record.step || JSON.stringify(record))
      }
      return String(item ?? '')
    })
    .filter(Boolean)
}
</script>
