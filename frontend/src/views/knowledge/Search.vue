<template>
  <PageFrame title="知识检索" code="KNOWLEDGE / SEARCH" description="调用后端检索问答接口，返回真实参考来源（references）与检索片段（retrieved_chunks）。">
    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="检索条件">
        <form class="grid gap-3" @submit.prevent="submit">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            问题
            <textarea v-model.trim="form.query" class="scada-input min-h-32" placeholder="例如：逆变器告警后如何排查？" required></textarea>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              厂家
              <select v-model="form.manufacturer" class="scada-input">
                <option value="">不限厂家</option>
                <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              产品系列
              <select v-model="form.product_series" class="scada-input">
                <option value="">不限系列</option>
                <option v-for="item in productSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </div>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            文档类型
            <select v-model="form.document_type" class="scada-input">
              <option value="">不限类型</option>
              <option v-for="item in documentTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            返回片段数（top_k）
            <input v-model.number="form.top_k" class="scada-input" min="1" max="10" type="number" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            检索模式
            <select v-model="form.retrieval_mode" class="scada-input">
              <option value="hybrid">混合检索</option>
              <option value="keyword">关键词检索</option>
              <option value="vector">向量检索</option>
            </select>
          </label>
          <button class="scada-button primary" type="submit" :disabled="loading">
            <Search :size="16" />
            {{ loading ? '检索中' : '检索知识库' }}
          </button>
        </form>
      </DataPanel>

      <DataPanel title="检索回答">
        <div v-if="result" class="space-y-4">
          <div class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-cyan-200">
              <span>trace_id: {{ result.trace_id }}</span>
              <span>置信度（confidence）：{{ Math.round(result.confidence * 100) }}%</span>
              <span>检索模式：{{ retrievalModeLabel(result.retrieval_mode) }}</span>
              <span>vector_backend：{{ result.vector_backend || 'unavailable' }}</span>
            </div>
            <p v-if="result.vector_fallback_used" class="mb-2 rounded border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-xs text-amber-100">
              向量检索不可用，已回退关键词检索。
            </p>
            <p class="whitespace-pre-wrap text-sm leading-7 text-slate-100">{{ result.answer }}</p>
          </div>

          <section>
            <h3 class="mb-2 text-sm font-black text-white">建议步骤</h3>
            <ol class="space-y-2 text-sm text-slate-300">
              <li v-for="(step, index) in result.suggested_steps" :key="`${step}-${index}`" class="rounded-md bg-white/[0.03] px-3 py-2">
                {{ index + 1 }}. {{ step }}
              </li>
            </ol>
          </section>

          <section>
            <h3 class="mb-2 text-sm font-black text-white">真实来源</h3>
            <div v-if="result.references.length" class="grid gap-2">
              <div v-for="ref in result.references" :key="`${ref.document_id}-${ref.chunk_index}`" class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
                <div class="font-bold text-white">{{ ref.document_title || ref.document_id }}</div>
                <div class="mt-1 text-xs text-slate-400">
                  {{ labelOf(ref.manufacturer) }} / {{ ref.product_series || '-' }} / {{ labelOf(ref.document_type) }} / 切片 {{ ref.chunk_index }} / 相关度 {{ formatScore(ref.score) }}
                </div>
                <p v-if="ref.quote" class="mt-2 line-clamp-3 text-xs leading-6 text-slate-400">{{ ref.quote }}</p>
              </div>
            </div>
            <EmptyState v-else text="当前知识库未检索到足够相关资料，请补充华为或阳光电源光伏逆变器手册、故障案例或巡检规范。" />
          </section>
        </div>
        <EmptyState v-else text="提交检索问题后显示回答、来源和切片。" />
      </DataPanel>
    </div>

    <DataPanel v-if="result?.retrieved_chunks.length" title="检索片段" subtitle="后端返回的检索片段（retrieved_chunks）原文。">
      <div class="space-y-3">
        <article v-for="chunk in result.retrieved_chunks" :key="chunk.chunk_id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span class="font-mono text-cyan-200">相关度 {{ formatScore(chunk.score) }}</span>
            <span>关键词 {{ formatScore(chunk.keyword_score ?? undefined) }}</span>
            <span>向量 {{ formatScore(chunk.vector_score ?? undefined) }}</span>
            <span>综合 {{ formatScore(chunk.hybrid_score ?? undefined) }}</span>
            <span>来源 {{ retrievalSourceLabel(chunk.retrieval_source) }}</span>
            <span>{{ chunk.document_title }}</span>
            <span>{{ chunk.section_title || '未标注章节' }}</span>
          </div>
          <p class="whitespace-pre-wrap text-sm leading-7 text-slate-200">{{ chunk.content }}</p>
        </article>
      </div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { Search } from '@lucide/vue'
import { queryRetrievalApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import { documentTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { RetrievalResponse } from '@/types'

const result = ref<RetrievalResponse | null>(null)
const loading = ref(false)
const error = ref('')
const form = reactive({
  query: '',
  manufacturer: '',
  product_series: '',
  device_type: 'pv_inverter',
  document_type: '',
  top_k: 5,
  retrieval_mode: 'hybrid'
})

async function submit() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const payload: Record<string, unknown> = {
      query: form.query,
      device_type: 'pv_inverter',
      top_k: Math.min(10, Math.max(1, form.top_k)),
      retrieval_mode: form.retrieval_mode,
      enable_vector: form.retrieval_mode !== 'keyword'
    }
    if (form.manufacturer) payload.manufacturer = form.manufacturer
    if (form.product_series) payload.product_series = form.product_series
    if (form.document_type) payload.document_type = form.document_type
    result.value = await queryRetrievalApi(payload)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '知识检索失败'
  } finally {
    loading.value = false
  }
}

function labelOf(value?: string | null) {
  const options = [...manufacturerOptions, ...documentTypeOptions]
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatScore(value?: number) {
  return typeof value === 'number' ? value.toFixed(2) : '-'
}

function retrievalModeLabel(value?: string) {
  return ({ keyword: '关键词', vector: '向量', hybrid: '混合' } as Record<string, string>)[value || ''] ?? value ?? '-'
}

function retrievalSourceLabel(value?: string) {
  return ({ keyword: '关键词', vector: '向量', hybrid: '混合命中' } as Record<string, string>)[value || ''] ?? value ?? '-'
}
</script>
