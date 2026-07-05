<template>
  <DataPanel title="外部 Provider 状态" subtitle="未配置真实 API 时不会外呼；dry-run 仅构造请求，mock-run 仅用于本地联调。">
    <template #actions>
      <button class="scada-button !min-h-8 !px-3" type="button" :disabled="loading" @click="$emit('refresh')">刷新</button>
    </template>
    <div class="grid gap-3 xl:grid-cols-2">
      <article v-for="provider in providers" :key="provider.provider_code" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <h3 class="font-black text-white">{{ provider.provider_name }}</h3>
              <MultimodalStatusPill :value="provider.status" />
            </div>
            <p class="mt-1 text-xs text-slate-400">
              {{ provider.provider_code }} / {{ provider.provider_type }} / configured={{ provider.configured ? 'yes' : 'no' }}
            </p>
            <p class="mt-1 text-xs text-slate-500">capabilities：{{ provider.capabilities.join(', ') || '-' }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="scada-button !min-h-8 !px-3" type="button" :disabled="!canCheck" @click="$emit('check', provider.provider_code)">检查</button>
            <button class="scada-button !min-h-8 !px-3" type="button" :disabled="readonly" @click="$emit('dry-run', provider.provider_code)">dry-run</button>
            <button class="scada-button primary !min-h-8 !px-3" type="button" :disabled="!canMock" @click="$emit('mock-run', provider.provider_code)">mock-run</button>
            <button v-if="canReal" class="scada-button danger !min-h-8 !px-3" type="button" @click="$emit('real-run', provider.provider_code)">real-run</button>
          </div>
        </div>
      </article>
    </div>
    <div v-if="lastResult" class="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
      <div class="flex flex-wrap items-center gap-2">
        <span class="font-bold text-cyan-50">最近调用结果</span>
        <MultimodalStatusPill :value="lastResult.status" />
        <span class="font-mono text-xs text-slate-300">trace_id={{ lastResult.trace_id }}</span>
        <span class="text-xs text-slate-300">external_api_called={{ String(lastResult.external_api_called) }}</span>
      </div>
      <details class="mt-2">
        <summary class="cursor-pointer text-xs font-bold text-cyan-100">脱敏请求/响应摘要</summary>
        <pre class="mt-2 max-h-64 overflow-auto rounded bg-black/40 p-3 text-xs text-slate-300">{{ pretty(lastResult) }}</pre>
      </details>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { ExternalApiGatewayResult, ExternalApiProviderStatus } from '@/types'

defineProps<{
  providers: ExternalApiProviderStatus[]
  loading?: boolean
  readonly?: boolean
  canCheck?: boolean
  canMock?: boolean
  canReal?: boolean
  lastResult?: ExternalApiGatewayResult | null
}>()

defineEmits<{
  refresh: []
  check: [providerCode: string]
  'dry-run': [providerCode: string]
  'mock-run': [providerCode: string]
  'real-run': [providerCode: string]
}>()

function pretty(value: unknown) {
  return JSON.stringify(value || {}, null, 2)
}
</script>
