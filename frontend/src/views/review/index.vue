<template>
  <PageFrame title="知识审核" code="REVIEW / KNOWLEDGE" description="审核已上传的光伏逆变器检修文档，控制资料是否进入正式知识库。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadDocuments">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <DataPanel title="待审核文档">
      <div class="mb-4 grid gap-3 md:grid-cols-4">
        <select v-model="filters.review_status" class="scada-input">
          <option value="">不限状态</option>
          <option value="draft">草稿</option>
          <option value="pending_review">待审核</option>
          <option value="approved">已通过</option>
          <option value="rejected">已驳回</option>
          <option value="archived">已归档</option>
        </select>
        <select v-model="filters.manufacturer" class="scada-input">
          <option value="">不限厂家</option>
          <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索文档标题" />
        <button class="scada-button" type="button" @click="loadDocuments">
          <Search :size="16" />
          查询
        </button>
      </div>

      <div v-if="documents.length" class="space-y-3">
        <article v-for="doc in documents" :key="String(doc.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 class="font-black text-white">{{ doc.title }}</h3>
              <p class="mt-1 text-xs text-slate-400">
                {{ labelOf(doc.manufacturer as string) }} / {{ doc.product_series || '-' }} / {{ labelOf(doc.document_type as string) }}
              </p>
              <p class="mt-2 text-sm text-slate-300">切片：{{ doc.chunk_count ?? 0 }} · 解析：{{ formatStatusLabel(doc.parse_status as string) }}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <StatusPill :value="String(doc.review_status || doc.status || 'draft')" />
              <button class="scada-button !min-h-8 !px-3" type="button" @click="approve(String(doc.id))">通过</button>
              <button class="scada-button !min-h-8 !px-3" type="button" @click="reject(String(doc.id))">驳回</button>
              <button class="scada-button !min-h-8 !px-3" type="button" @click="archive(String(doc.id))">归档</button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无待审核知识文档" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RefreshCcw, Search } from '@lucide/vue'
import { approveKnowledgeApi, archiveKnowledgeApi, getReviewKnowledgeApi, rejectKnowledgeApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { documentTypeOptions, manufacturerOptions } from '@/types'
import { formatStatusLabel } from '@/utils/display'

const documents = ref<Record<string, unknown>[]>([])
const loading = ref(false)
const error = ref('')
const filters = reactive({ review_status: '', manufacturer: '', keyword: '' })

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50 }
    if (filters.review_status) params.review_status = filters.review_status
    if (filters.manufacturer) params.manufacturer = filters.manufacturer
    if (filters.keyword) params.keyword = filters.keyword
    const result = await getReviewKnowledgeApi(params)
    documents.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '审核文档读取失败'
    documents.value = []
  } finally {
    loading.value = false
  }
}

async function approve(id: string) {
  await action(() => approveKnowledgeApi(id, '前端审核通过'), '文档已通过')
}

async function reject(id: string) {
  await action(() => rejectKnowledgeApi(id, '前端审核驳回'), '文档已驳回')
}

async function archive(id: string) {
  await action(() => archiveKnowledgeApi(id, '前端归档'), '文档已归档')
}

async function action(fn: () => Promise<unknown>, message: string) {
  error.value = ''
  try {
    await fn()
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
    await loadDocuments()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '审核操作失败'
  }
}

function labelOf(value?: string | null) {
  const options = [...manufacturerOptions, ...documentTypeOptions]
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

onMounted(loadDocuments)
</script>
