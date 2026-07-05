<template>
  <DataPanel title="智能体产物" subtitle="多模态证据摘要、安全清单和追溯摘要均由后端 artifact 记录保存。">
    <div v-if="artifacts.length" class="grid gap-3 md:grid-cols-2">
      <article v-for="item in artifacts" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">{{ item.artifact_type }}</div>
        <h3 class="mt-1 font-black text-white">{{ item.title || item.id }}</h3>
        <p class="mt-2 text-sm text-slate-300">{{ item.content_text || '暂无文本摘要' }}</p>
        <details class="mt-2">
          <summary class="cursor-pointer text-xs font-bold text-cyan-200">草稿 JSON</summary>
          <pre class="mt-2 max-h-52 overflow-auto rounded bg-black/40 p-3 text-xs text-slate-300">{{ pretty(item.content_json || {}) }}</pre>
        </details>
      </article>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">暂无草稿产物。</div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import type { AgentArtifact } from '@/types/agent'

defineProps<{ artifacts: AgentArtifact[] }>()

function pretty(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
