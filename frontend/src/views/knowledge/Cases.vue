<template>
  <PageFrame title="故障案例" code="KNOWLEDGE / CASES" description="基于后端已保存的检索问答记录展示可追溯案例，不使用前端假数据。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadRecords">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <DataPanel title="问答沉淀" subtitle="来自 /api/retrieval/records，可用于复盘故障问答与来源。">
      <div v-if="records.length" class="space-y-3">
        <article v-for="record in records" :key="String(record.id || record.trace_id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 class="font-black text-white">{{ String(record.question || record.normalized_query || '未命名问题') }}</h3>
              <p class="mt-2 line-clamp-3 text-sm leading-7 text-slate-300">{{ String(record.answer || '暂无回答摘要') }}</p>
              <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                <span>trace_id：{{ record.trace_id || '-' }}</span>
                <span>厂家：{{ labelOf(record.manufacturer as string) }}</span>
                <span>系列：{{ record.product_series || '-' }}</span>
                <span>创建时间：{{ formatTime(record.created_at as string) }}</span>
              </div>
            </div>
            <StatusPill value="info" :label="`置信度 ${formatConfidence(record.confidence)}`" />
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无已保存问答记录；请先在检修问答或知识检索页面提交问题。" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RefreshCcw } from '@lucide/vue'
import { getRetrievalRecordsApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'

const records = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const error = ref('')

async function loadRecords() {
  loading.value = true
  error.value = ''
  try {
    const result = await getRetrievalRecordsApi({ page: 1, page_size: 20 })
    records.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '故障案例记录读取失败'
    records.value = []
  } finally {
    loading.value = false
  }
}

function labelOf(value?: string | null) {
  const map: Record<string, string> = { huawei: '华为', sungrow: '阳光电源' }
  return value ? map[value] ?? value : '-'
}

function formatConfidence(value: unknown) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

onMounted(loadRecords)
</script>
