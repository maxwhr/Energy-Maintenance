<template>
  <PageFrame title="人工修正" code="CORRECTIONS / REVIEW" description="提交和处理问答、诊断、SOP 或任务结果的人工作业修正记录。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadCorrections">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
      <DataPanel title="提交修正" subtitle="用于把现场确认后的正确结论反馈给后端修正记录表。">
        <form class="grid gap-3" @submit.prevent="createCorrection">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            来源类型
            <select v-model="form.source_type" class="scada-input">
              <option value="qa">问答</option>
              <option value="diagnosis">诊断</option>
              <option value="sop">SOP</option>
              <option value="task">任务</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            来源 trace_id
            <input v-model.trim="form.source_trace_id" class="scada-input" required placeholder="选择或粘贴需要修正的 trace_id" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            原始输出
            <textarea v-model.trim="form.original_output" class="scada-input min-h-24" required placeholder="可填写文本或 JSON"></textarea>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            修正后输出
            <textarea v-model.trim="form.corrected_output" class="scada-input min-h-24" required placeholder="可填写文本或 JSON"></textarea>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            修正原因
            <textarea v-model.trim="form.reason" class="scada-input min-h-20" placeholder="说明现场依据、厂家手册或专家判断"></textarea>
          </label>
          <button class="scada-button primary" type="submit" :disabled="saving">
            <Plus :size="16" />
            {{ saving ? '提交中' : '提交修正' }}
          </button>
        </form>
      </DataPanel>

      <DataPanel title="修正记录" subtitle="管理员或专家可将修正处理为采纳（accept）或拒绝（reject）。">
        <div class="mb-4 grid gap-3 md:grid-cols-4">
          <select v-model="filters.source_type" class="scada-input">
            <option value="">全部来源</option>
            <option value="qa">问答</option>
            <option value="diagnosis">诊断</option>
            <option value="sop">SOP</option>
            <option value="task">任务</option>
          </select>
          <select v-model="filters.review_status" class="scada-input">
            <option value="">全部状态</option>
            <option value="pending">待处理</option>
            <option value="accepted">已采纳</option>
            <option value="rejected">已拒绝</option>
          </select>
          <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索 trace_id" />
          <button class="scada-button" type="button" @click="loadCorrections">
            <Search :size="16" />
            查询
          </button>
        </div>

        <div v-if="corrections.length" class="space-y-3">
          <article v-for="item in corrections" :key="String(item.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 class="font-black text-white">{{ formatRecordTypeLabel(item.source_type as string) }} / {{ item.source_trace_id }}</h3>
                <p class="mt-2 line-clamp-2 text-sm leading-6 text-slate-300">{{ item.correction_reason || item.reason || '未填写原因' }}</p>
                <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-400">
                  <span>{{ formatTime(item.created_at as string) }}</span>
                  <span>提交人：{{ item.submitted_by_name || '-' }}</span>
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <StatusPill :value="String(item.review_status || 'pending')" />
                <button class="scada-button !min-h-8 !px-3" type="button" @click="showDetail(item)">详情</button>
                <button v-if="canResolve" class="scada-button !min-h-8 !px-3" type="button" @click="resolve(item, 'accept')">采纳</button>
                <button v-if="canResolve" class="scada-button !min-h-8 !px-3" type="button" @click="resolve(item, 'reject')">拒绝</button>
              </div>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无修正记录" />
      </DataPanel>
    </div>

    <DataPanel v-if="detail" title="修正详情">
      <div class="grid gap-3 md:grid-cols-3">
        <div v-for="item in detailRows" :key="item.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
          <div class="text-xs font-bold text-slate-400">{{ item.label }}</div>
          <div class="mt-1 break-words text-sm font-bold text-white">{{ item.value }}</div>
        </div>
      </div>
      <div class="mt-4 grid gap-4 lg:grid-cols-2">
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">原始输出</h3>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">{{ summarizePayload(detail.original_output) }}</p>
        </section>
        <section class="rounded-md border border-emerald-300/20 bg-emerald-400/10 p-4">
          <h3 class="text-sm font-black text-white">修正输出</h3>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-200">{{ summarizePayload(detail.corrected_output) }}</p>
        </section>
      </div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Plus, RefreshCcw, Search } from '@lucide/vue'
import { createCorrectionApi, getCorrectionsApi, resolveCorrectionApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useUserStore } from '@/stores/user'
import { formatRecordTypeLabel, formatReviewStatusLabel } from '@/utils/display'

const userStore = useUserStore()
const corrections = ref<Record<string, unknown>[]>([])
const detail = ref<Record<string, unknown> | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const filters = reactive({ source_type: '', review_status: '', keyword: '' })
const form = reactive({
  source_type: 'qa',
  source_trace_id: '',
  original_output: '',
  corrected_output: '',
  reason: ''
})

const canResolve = computed(() => userStore.roles.includes('admin') || userStore.roles.includes('expert'))
const detailRows = computed(() => {
  if (!detail.value) return []
  return [
    { label: '来源类型', value: formatRecordTypeLabel(detail.value.source_type as string) },
    { label: 'trace_id', value: String(detail.value.source_trace_id || '-') },
    { label: '审核状态', value: formatReviewStatusLabel(detail.value.review_status as string) },
    { label: '修正原因', value: String(detail.value.correction_reason || detail.value.reason || '-') },
    { label: '提交人', value: String(detail.value.submitted_by_name || '-') },
    { label: '创建时间', value: formatTime(detail.value.created_at as string) }
  ]
})

async function loadCorrections() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50 }
    if (filters.source_type) params.source_type = filters.source_type
    if (filters.review_status) params.review_status = filters.review_status
    if (filters.keyword) params.keyword = filters.keyword
    const result = await getCorrectionsApi(params)
    corrections.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '修正记录读取失败'
    corrections.value = []
  } finally {
    loading.value = false
  }
}

async function createCorrection() {
  saving.value = true
  error.value = ''
  try {
    await createCorrectionApi({
      source_type: form.source_type,
      source_trace_id: form.source_trace_id,
      original_output: parsePayload(form.original_output),
      corrected_output: parsePayload(form.corrected_output),
      reason: form.reason || undefined
    })
    toast('修正记录已提交')
    form.source_trace_id = ''
    form.original_output = ''
    form.corrected_output = ''
    form.reason = ''
    await loadCorrections()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '修正提交失败'
  } finally {
    saving.value = false
  }
}

async function resolve(item: Record<string, unknown>, action: 'accept' | 'reject') {
  const id = String(item.id)
  const label = action === 'accept' ? '采纳' : '拒绝'
  if (!window.confirm(`确认${label}该修正？`)) return
  error.value = ''
  try {
    await resolveCorrectionApi(id, {
      action,
      review_comment: `前端${label}修正`
    })
    toast(`修正已${label}`)
    await loadCorrections()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '修正处理失败'
  }
}

function showDetail(item: Record<string, unknown>) {
  detail.value = item
}

function parsePayload(value: string) {
  try {
    return JSON.parse(value)
  } catch {
    return { text: value }
  }
}

function summarizePayload(value: unknown) {
  if (!value) return '-'
  if (typeof value === 'string') return value
  if (typeof value === 'object' && value && 'text' in value) {
    return String((value as Record<string, unknown>).text || '-')
  }
  return JSON.stringify(value, null, 2)
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(loadCorrections)
</script>
