<template>
  <DataPanel v-if="suggestion" title="知识图谱候选建议" subtitle="仅生成候选节点和关系建议，不写入正式知识图谱。">
    <div class="grid gap-3 md:grid-cols-2">
      <ListBlock title="候选节点" :items="nodeItems" />
      <ListBlock title="候选关系" :items="edgeItems" />
    </div>
    <div class="mt-3 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
      <span class="font-bold text-white">审核要求：</span>
      {{ suggestion.requires_kg_review ? '需要知识图谱审核' : '未标记审核要求' }}；本任务未创建正式 KG 节点或边。
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import ListBlock from '@/components/MultimodalListBlock.vue'

const props = defineProps<{ suggestion?: Record<string, unknown> | null }>()

const nodeItems = computed(() => toList(props.suggestion?.candidate_nodes).map((item) => {
  const node = item as Record<string, unknown>
  return `${node.node_type || '-'} / ${node.name || '-'} / ${node.confidence ?? '-'}`
}))

const edgeItems = computed(() => toList(props.suggestion?.candidate_edges).map((item) => {
  const edge = item as Record<string, unknown>
  return `${edge.source || '-'} -> ${edge.relation || '-'} -> ${edge.target || '-'}`
}))

function toList(value: unknown) {
  return Array.isArray(value) ? value : []
}
</script>
