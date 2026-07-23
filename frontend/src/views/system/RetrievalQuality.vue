<template>
  <PageFrame
    title="检索运行状态"
    code="RAG / STATUS"
    description="展示正式检索范围、知识来源、引用有效性和可选检索组件状态。"
  >
    <template #actions>
      <button
        class="scada-button"
        type="button"
        :disabled="loading"
        @click="loadAll"
      >
        刷新
      </button>
    </template>

    <div
      v-if="error"
      class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200"
    >
      {{ error }}
    </div>

    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <DataPanel
        v-for="item in productionCards"
        :key="item.label"
        :title="item.label"
      >
        <div class="text-xl font-black text-white">{{ item.value }}</div>
        <p class="mt-2 text-xs leading-5 text-slate-400">{{ item.detail }}</p>
      </DataPanel>
    </div>

    <DataPanel
      title="正式检索边界"
      subtitle="PostgreSQL 是知识与 Citation 的事实来源。"
      data-testid="production-retrieval-summary"
    >
      <div class="grid gap-3 text-sm md:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="item in productionDetails"
          :key="item.label"
          class="rounded bg-white/[0.03] p-3"
        >
          <div class="text-xs text-slate-400">{{ item.label }}</div>
          <div class="mt-1 font-semibold text-slate-100">{{ item.value }}</div>
        </div>
      </div>
      <p class="mt-4 text-xs leading-5 text-amber-100">
        知识不足时返回受控拒答；禁止生成虚假 Citation，禁止跨厂家引用。
      </p>
    </DataPanel>

    <div
      v-if="!labEnabled"
      class="rounded-md border border-slate-500/30 bg-slate-500/10 p-4 text-sm text-slate-300"
      data-testid="retrieval-lab-disabled"
    >
      检索实验室已关闭。当前页面不会请求研发实验状态接口。
    </div>

    <template v-else>
      <DataPanel
        title="检索实验室"
        subtitle="仅在 ENABLE_RETRIEVAL_LAB=true 时加载研发状态。"
        data-testid="retrieval-lab-panel"
      >
        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div
            v-for="item in labCards"
            :key="item.label"
            class="rounded border border-cyan-300/20 bg-cyan-400/10 p-3"
          >
            <div class="font-mono text-xs text-cyan-200">{{ item.label }}</div>
            <div class="mt-2 break-words text-sm font-semibold text-white">
              {{ item.value }}
            </div>
          </div>
        </div>
      </DataPanel>
    </template>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getR5RetrievalQualitySummaryApi,
  getRetrievalR1ScopeStatusApi,
  getRetrievalR2ScopeStatusApi,
  getRetrievalR3ScopeStatusApi,
  getRetrievalR4ScopeStatusApi,
  getRetrievalStrategyStatusApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { isRetrievalLabEnabled } from '@/utils/retrievalLab'

const loading = ref(false)
const error = ref('')
const strategyStatus = ref<Record<string, any>>({})
const labStatuses = ref<Record<string, Record<string, any>>>({})

const labEnabled = computed(() => isRetrievalLabEnabled(strategyStatus.value))

const productionCards = computed(() => [
  {
    label: '默认检索策略',
    value: strategyStatus.value.default_strategy || 'keyword',
    detail: `回退策略：${strategyStatus.value.fallback_strategy || 'keyword'}`
  },
  {
    label: '正式知识',
    value: `${strategyStatus.value.approved_active_document_count ?? 0} / ${strategyStatus.value.approved_active_chunk_count ?? 0}`,
    detail: 'approved + active 文档 / 切片'
  },
  {
    label: 'Citation 有效率',
    value: percent(strategyStatus.value.citation_validity_rate),
    detail: `${strategyStatus.value.valid_citation_count ?? 0} / ${strategyStatus.value.citation_count ?? 0}`
  },
  {
    label: '最近正式索引',
    value: strategyStatus.value.latest_formal_index?.status || 'not_run',
    detail: strategyStatus.value.latest_formal_index?.backend || '未配置'
  }
])

const productionDetails = computed(() => [
  {
    label: '厂家范围',
    value: (strategyStatus.value.manufacturers || []).join(' / ') || 'huawei / sungrow'
  },
  {
    label: '受控拒答',
    value: enabledLabel(strategyStatus.value.controlled_refusal_enabled)
  },
  {
    label: 'Vector / Embedding / Rerank',
    value: [
      enabledLabel(strategyStatus.value.vector_enabled),
      enabledLabel(strategyStatus.value.embedding_enabled),
      enabledLabel(strategyStatus.value.rerank_enabled)
    ].join(' / ')
  },
  {
    label: '外部 Provider',
    value: strategyStatus.value.external_provider_configured ? '已配置' : '未配置'
  }
])

const labCards = computed(() => [
  {
    label: 'R1',
    value: labStatuses.value.r1?.canary_status || 'NOT_RUN'
  },
  {
    label: 'R2',
    value: labStatuses.value.r2?.quality_gate_status || 'NOT_RUN'
  },
  {
    label: 'R3',
    value: labStatuses.value.r3?.canary?.status || 'NOT_RUN'
  },
  {
    label: 'R4',
    value: labStatuses.value.r4?.canary?.status || 'NOT_RUN'
  },
  {
    label: 'R5',
    value: `${labStatuses.value.r5?.artifact_count ?? 0} artifacts`
  }
])

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    strategyStatus.value = await getRetrievalStrategyStatusApi()
    if (!isRetrievalLabEnabled(strategyStatus.value)) {
      labStatuses.value = {}
      return
    }
    const [r1, r2, r3, r4, r5] = await Promise.all([
      getRetrievalR1ScopeStatusApi(),
      getRetrievalR2ScopeStatusApi(),
      getRetrievalR3ScopeStatusApi(),
      getRetrievalR4ScopeStatusApi(),
      getR5RetrievalQualitySummaryApi()
    ])
    labStatuses.value = { r1, r2, r3, r4, r5 }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '检索状态读取失败'
  } finally {
    loading.value = false
  }
}

function percent(value: unknown) {
  return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '0.0%'
}

function enabledLabel(value: unknown) {
  return value === true ? '已启用' : '未启用'
}

onMounted(loadAll)
</script>
