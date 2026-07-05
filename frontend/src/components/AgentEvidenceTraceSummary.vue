<template>
  <DataPanel v-if="trace" title="知识沉淀证据追溯" subtitle="展示草稿来源 run、artifact、媒体、知识引用、图谱上下文和审批记录。">
    <div class="grid gap-3 md:grid-cols-3">
      <section v-for="group in groups" :key="group.title" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <h3 class="font-black text-white">{{ group.title }}</h3>
        <ul v-if="group.items.length" class="mt-2 space-y-1 text-xs text-slate-300">
          <li v-for="item in group.items" :key="item" class="break-all">- {{ item }}</li>
        </ul>
        <p v-else class="mt-2 text-xs text-slate-500">暂无</p>
      </section>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'

const props = defineProps<{ trace?: Record<string, unknown> | null }>()

const groups = computed(() => [
  { title: '来源 Run', items: toTextList(props.trace?.source_agent_run_ids) },
  { title: '来源 Artifact', items: toTextList(props.trace?.source_artifact_ids) },
  { title: '媒体证据', items: toTextList(props.trace?.media_ids) },
  { title: '知识引用', items: toTextList(props.trace?.knowledge_reference_ids) },
  { title: '图谱引用', items: toTextList(props.trace?.kg_reference_ids) },
  { title: '审批记录', items: toTextList(props.trace?.approval_ids) }
])

function toTextList(value: unknown) {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : []
}
</script>
