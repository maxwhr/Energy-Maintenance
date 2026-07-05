<template>
  <DataPanel title="智能体工具调用" subtitle="所有工具调用均来自后端真实记录，blocked/mock/dry-run 状态会明确展示。">
    <div v-if="calls.length" class="overflow-auto">
      <table class="w-full min-w-[760px] text-left text-sm">
        <thead class="text-xs text-slate-400">
          <tr>
            <th class="px-3 py-2">工具</th>
            <th class="px-3 py-2">状态</th>
            <th class="px-3 py-2">耗时</th>
            <th class="px-3 py-2">摘要</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="call in calls" :key="call.id" class="border-t border-slate-600/20">
            <td class="px-3 py-3 font-mono text-xs text-cyan-100">{{ call.tool_name }}</td>
            <td class="px-3 py-3"><MultimodalStatusPill :value="call.status" /></td>
            <td class="px-3 py-3 text-slate-300">{{ call.latency_ms ?? '-' }} ms</td>
            <td class="px-3 py-3 text-slate-300">
              {{ (call.output_json?.summary as string) || call.error_message || '-' }}
              <details class="mt-2">
                <summary class="cursor-pointer text-xs font-bold text-cyan-200">技术 JSON</summary>
                <pre class="mt-2 max-h-52 overflow-auto rounded bg-black/40 p-3 text-xs text-slate-300">{{ pretty(call.output_json || {}) }}</pre>
              </details>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">暂无工具调用。</div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { AgentToolCall } from '@/types/agent'

defineProps<{ calls: AgentToolCall[] }>()

function pretty(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
