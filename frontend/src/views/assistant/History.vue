<template>
  <PageFrame title="问答记录" code="RETRIEVAL / RECORDS" description="读取后端问答记录（qa_records），核对 trace_id、回答和来源追溯。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadRecords">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <DataPanel title="历史问答">
      <div v-if="records.length" class="space-y-3">
        <article v-for="record in records" :key="String(record.trace_id || record.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 class="font-black text-white">{{ String(record.question || record.normalized_query || '未命名问题') }}</h3>
              <p class="mt-2 line-clamp-3 text-sm leading-7 text-slate-300">{{ String(record.answer || '暂无回答') }}</p>
              <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                <span>trace_id：{{ record.trace_id || '-' }}</span>
                <span>{{ formatTime(record.created_at as string) }}</span>
              </div>
            </div>
            <StatusPill value="info" :label="`置信度 ${formatConfidence(record.confidence)}`" />
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无问答记录" />
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
    const result = await getRetrievalRecordsApi({ page: 1, page_size: 30 })
    records.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '问答记录读取失败'
    records.value = []
  } finally {
    loading.value = false
  }
}

function formatConfidence(value: unknown) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

onMounted(loadRecords)
</script>
