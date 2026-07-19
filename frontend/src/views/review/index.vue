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
      <div class="mb-4 rounded border border-cyan-300/20 bg-cyan-400/10 p-3 text-xs leading-5 text-cyan-100">
        华为官方资料仅表示公开来源已核验，不代表允许重新分发。严格质量门禁可产生“开发工程审批（Pilot only）”，它不等于人工专家审核；expert_verified 只能由真实 expert/admin 人工操作产生。
      </div>
      <div v-if="!canReview" class="mb-4 rounded border border-amber-300/20 bg-amber-400/10 p-3 text-xs leading-5 text-amber-100">
        当前账号为只读审核视图；可查看元数据、来源和文档预览，不能批准、退回、标记或归档。
      </div>
      <div class="mb-4 grid gap-3 md:grid-cols-3 xl:grid-cols-8">
        <select v-model="filters.language_scope" class="scada-input" aria-label="知识语言范围" @change="loadDocuments">
          <option value="zh-CN">中文主知识</option>
          <option value="en">英文备用资料</option>
          <option value="all">全部语言</option>
        </select>
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
        <input v-model.trim="filters.product_series" class="scada-input" placeholder="产品族，如 SUN2000" />
        <select v-model="filters.equipment_category" class="scada-input">
          <option value="">不限设备类别</option>
          <option v-for="item in equipmentCategories" :key="item" :value="item">{{ item }}</option>
        </select>
        <select v-model="filters.document_type" class="scada-input">
          <option value="">不限文档类型</option>
          <option value="FAQ_TROUBLESHOOTING">FAQ_TROUBLESHOOTING</option>
          <option value="ALARM_REFERENCE">ALARM_REFERENCE</option>
          <option value="USER_MANUAL">USER_MANUAL</option>
          <option v-for="item in documentTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <select v-model="filters.quality_status" class="scada-input">
          <option value="">不限质量</option>
          <option value="READY_FOR_HUMAN_REVIEW">READY_FOR_HUMAN_REVIEW</option>
          <option value="NEEDS_METADATA">NEEDS_METADATA</option>
          <option value="NEEDS_OCR">NEEDS_OCR</option>
          <option value="MARKETING_ONLY">MARKETING_ONLY</option>
        </select>
        <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索文档标题" />
        <button class="scada-button" type="button" @click="loadDocuments">
          <Search :size="16" />
          查询
        </button>
      </div>

      <div v-if="canReview && selectedIds.length" class="mb-4 flex flex-wrap items-center gap-3 rounded bg-white/[0.03] p-3 text-sm">
        <span>已明确选择 {{ selectedIds.length }}/10 份资料</span>
        <span v-for="doc in selectedDocuments" :key="String(doc.id)" class="rounded bg-black/30 px-2 py-1 text-xs">
          {{ doc.title }} · {{ sourceDomain(doc) }} · {{ metadata(doc).quality_status }}
        </span>
        <button class="scada-button primary" type="button" :disabled="selectedIds.length > 10" @click="batchApprove">确认批量批准进入 Pilot</button>
        <button class="scada-button" type="button" @click="selectedIds = []">清空</button>
      </div>

      <div v-if="visibleDocuments.length" class="space-y-3">
        <article v-for="doc in visibleDocuments" :key="String(doc.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div class="flex items-center gap-2">
                <input v-if="canReview && batchEligible(doc)" v-model="selectedIds" type="checkbox" :value="String(doc.id)" aria-label="选择官方资料" @change="enforceSelectionLimit" />
                <h3 class="font-black text-white">{{ doc.title }}</h3>
                <span v-if="isVendorOfficial(doc)" class="rounded bg-cyan-400/15 px-2 py-1 text-[10px] font-bold text-cyan-200">华为官方来源</span>
                <span v-if="metadata(doc).engineering_approved_for_pilot" class="rounded bg-emerald-400/15 px-2 py-1 text-[10px] font-bold text-emerald-200">开发工程审批 · Pilot only</span>
                <span v-if="metadata(doc).engineering_approved_for_pilot" class="rounded bg-slate-400/15 px-2 py-1 text-[10px] font-bold text-slate-200">非人工专家审核</span>
                <span v-if="metadata(doc).normalized_language === 'zh-CN'" class="rounded bg-cyan-400/15 px-2 py-1 text-[10px] font-bold text-cyan-100">中文主知识</span>
                <span v-if="metadata(doc).normalized_language === 'en'" class="rounded bg-amber-400/15 px-2 py-1 text-[10px] font-bold text-amber-100">英文备用 · 未启用</span>
                <span v-if="requiresIndividualReview(doc)" class="rounded bg-amber-400/15 px-2 py-1 text-[10px] font-bold text-amber-200">必须逐份审核</span>
              </div>
              <p class="mt-1 text-xs text-slate-400">
                {{ labelOf(doc.manufacturer as string) }} / {{ doc.product_series || '-' }} / {{ labelOf(doc.document_type as string) }}
              </p>
              <p class="mt-2 text-sm text-slate-300">切片：{{ doc.chunk_count ?? 0 }} · 解析：{{ formatStatusLabel(doc.parse_status as string) }}</p>
              <div v-if="isVendorOfficial(doc)" class="mt-3 grid gap-1 text-xs text-slate-400 md:grid-cols-3">
                <span>产品族：{{ metadata(doc).product_family || '-' }}</span>
                <span>版本：{{ metadata(doc).document_version || '-' }}</span>
                <span>语言：{{ metadata(doc).language || '-' }}</span>
                <span>页数：{{ doc.page_count || '-' }}</span>
                <span>质量：{{ metadata(doc).quality_status || '-' }}</span>
                <span>规则：{{ metadata(doc).approval_rule_version || '-' }}</span>
                <span>专家验收：{{ metadata(doc).expert_verified === true ? '是' : '否' }}</span>
                <span>OCR：{{ metadata(doc).ocr_required ? '需要' : '不需要' }}</span>
                <span>设备类别：{{ (metadata(doc).equipment_categories || []).join(', ') || '-' }}</span>
                <span>告警：{{ alarmCount(doc) }}</span>
                <span>故障步骤：{{ metadata(doc).alarm_knowledge?.troubleshooting_steps || 0 }}</span>
                <span>安全动作：{{ metadata(doc).alarm_knowledge?.safety_actions || metadata(doc).safety_section_count || 0 }}</span>
                <span class="md:col-span-2">SHA-256：{{ metadata(doc).file_sha256 || '-' }}</span>
                <a v-if="doc.source" class="text-cyan-300 underline" :href="String(doc.source)" target="_blank" rel="noreferrer">原始官方来源</a>
                <span class="md:col-span-3">原文定位：{{ locatorText(doc) }}</span>
                <span v-if="doc.reviewed_by_name">审核人：{{ doc.reviewed_by_name }}</span>
                <span v-if="doc.reviewed_at" class="md:col-span-2">审核时间：{{ formatDateTime(doc.reviewed_at) }}</span>
              </div>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <StatusPill :value="String(doc.review_status || doc.status || 'draft')" />
              <button class="scada-button !min-h-8 !px-3" type="button" @click="togglePreview(String(doc.id))">{{ previewById[String(doc.id)] ? '收起预览' : '文档预览' }}</button>
              <button v-if="canReview && doc.review_status === 'pending_review' && approvalEligible(doc)" class="scada-button !min-h-8 !px-3" type="button" @click="approve(String(doc.id))">{{ isVendorOfficial(doc) ? '批准进入 Pilot' : '通过' }}</button>
              <button v-if="canReview && isVendorOfficial(doc) && doc.review_status === 'pending_review'" class="scada-button !min-h-8 !px-3" type="button" @click="flag(String(doc.id), 'needs_metadata')">退回补元数据</button>
              <button v-if="canReview && isVendorOfficial(doc) && doc.review_status === 'pending_review'" class="scada-button !min-h-8 !px-3" type="button" @click="flag(String(doc.id), 'needs_ocr')">标记需 OCR</button>
              <button v-if="canReview && isVendorOfficial(doc) && doc.review_status === 'pending_review'" class="scada-button !min-h-8 !px-3" type="button" @click="flag(String(doc.id), 'marketing_only')">标记营销资料</button>
              <button v-if="canReview && doc.review_status === 'pending_review'" class="scada-button !min-h-8 !px-3" type="button" @click="reject(String(doc.id))">驳回</button>
              <button v-if="canReview && isVendorOfficial(doc) && doc.review_status === 'approved'" class="scada-button !min-h-8 !px-3" type="button" @click="withdrawApproval(String(doc.id))">撤回批准</button>
              <button v-if="canReview" class="scada-button !min-h-8 !px-3" type="button" @click="archive(String(doc.id))">归档</button>
            </div>
          </div>
          <div v-if="previewById[String(doc.id)]" class="mt-4 rounded border border-slate-600/20 bg-black/30 p-3 text-xs text-slate-300">
            <div v-for="chunk in previewById[String(doc.id)].chunk_preview || []" :key="String(chunk.id)" class="mb-3 border-b border-white/5 pb-3">
              <strong>{{ chunk.section_title || '未命名章节' }}</strong>
              <p class="mt-1 whitespace-pre-wrap leading-5">{{ String(chunk.content || '').slice(0, 700) }}</p>
            </div>
            <div v-if="previewById[String(doc.id)].review_records?.length" class="mt-3">
              <strong>审核审计记录</strong>
              <div v-for="record in previewById[String(doc.id)].review_records" :key="String(record.id)" class="mt-2 rounded border border-white/5 p-2">
                {{ record.review_action }} · {{ record.before_status || '-' }} → {{ record.after_status || '-' }} · {{ formatDateTime(record.reviewed_at) }}
                <div v-if="record.review_comment" class="mt-1 text-slate-400">{{ record.review_comment }}</div>
              </div>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无待审核知识文档" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RefreshCcw, Search } from '@lucide/vue'
import { approveKnowledgeApi, archiveKnowledgeApi, batchApproveVendorOfficialApi, flagVendorOfficialApi, getReviewKnowledgeApi, getReviewKnowledgeDetailApi, rejectKnowledgeApi, withdrawVendorOfficialApprovalApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { documentTypeOptions, manufacturerOptions } from '@/types'
import { formatStatusLabel } from '@/utils/display'
import { useUserStore } from '@/stores/user'

const documents = ref<Record<string, unknown>[]>([])
const userStore = useUserStore()
const canReview = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const loading = ref(false)
const error = ref('')
const selectedIds = ref<string[]>([])
const previewById = ref<Record<string, any>>({})
const equipmentCategories = ['pv_inverter', 'energy_storage', 'power_optimizer', 'smart_guard', 'data_logger', 'plant_controller', 'communication_device', 'management_platform', 'mobile_app', 'other']
const filters = reactive({ language_scope: 'zh-CN', review_status: '', manufacturer: 'huawei', product_series: '', equipment_category: '', document_type: '', quality_status: '', keyword: '' })
const selectedDocuments = computed(() => documents.value.filter((item) => selectedIds.value.includes(String(item.id))))
const visibleDocuments = computed(() => documents.value.filter((item) => {
  if (filters.language_scope === 'all') return true
  return metadata(item).normalized_language === filters.language_scope
}))

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50 }
    if (filters.review_status) params.review_status = filters.review_status
    if (filters.manufacturer) params.manufacturer = filters.manufacturer
    if (filters.product_series) params.product_series = filters.product_series
    if (filters.equipment_category) params.equipment_category = filters.equipment_category
    if (filters.document_type) params.document_type = filters.document_type
    if (filters.quality_status) params.quality_status = filters.quality_status
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.language_scope !== 'all') params.normalized_language = filters.language_scope
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

async function withdrawApproval(id: string) {
  const reason = window.prompt('请输入撤回原因（至少 10 个字符）。撤回后文档将恢复为待审核，并标记为必须逐份审核。')
  if (!reason) return
  if (reason.trim().length < 10) {
    error.value = '撤回原因至少需要 10 个字符'
    return
  }
  if (!window.confirm('确认撤回此批准？该操作将写入 before/after、操作人、原因和审计事件。')) return
  await action(
    () => withdrawVendorOfficialApprovalApi(id, reason.trim(), 'pending_review'),
    '批准已审计化撤回，文档已恢复为待逐份审核'
  )
}

async function archive(id: string) {
  await action(() => archiveKnowledgeApi(id, '前端归档'), '文档已归档')
}

async function batchApprove() {
  const ids = [...selectedIds.value]
  if (!ids.length || ids.length > 10) return
  const lines = selectedDocuments.value.map((doc) => `${doc.title} | ${sourceDomain(doc)} | ${metadata(doc).quality_status}`)
  if (!window.confirm(`确认人工批准以下 ${ids.length} 份资料进入 pilot_r2？\n\n${lines.join('\n')}`)) return
  await action(
    () => batchApproveVendorOfficialApi(ids, `人工批量确认 ${ids.length} 份同一来源和产品族资料进入 pilot_r2`),
    `已人工批准 ${ids.length} 份官方资料`
  )
  selectedIds.value = []
}

async function flag(id: string, value: 'needs_metadata' | 'marketing_only' | 'needs_ocr') {
  await action(() => flagVendorOfficialApi(id, value, `人工标记：${value}`), `已标记 ${value}`)
}

async function togglePreview(id: string) {
  if (previewById.value[id]) {
    delete previewById.value[id]
    return
  }
  previewById.value[id] = await getReviewKnowledgeDetailApi(id)
}

function enforceSelectionLimit() {
  if (selectedIds.value.length > 10) {
    selectedIds.value = selectedIds.value.slice(0, 10)
    error.value = '单次最多选择 10 份资料'
  }
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

function isVendorOfficial(doc: Record<string, unknown>) {
  return doc.source_type === 'vendor_official' || metadata(doc).source_provenance === 'VENDOR_OFFICIAL'
}

function metadata(doc: Record<string, unknown>): Record<string, any> {
  return (doc.metadata_json || {}) as Record<string, any>
}

function batchEligible(doc: Record<string, unknown>) {
  return isVendorOfficial(doc) && doc.review_status === 'pending_review' && metadata(doc).quality_status === 'READY_FOR_HUMAN_REVIEW' && !requiresIndividualReview(doc)
}

function requiresIndividualReview(doc: Record<string, unknown>) {
  return metadata(doc).requires_individual_review === true || metadata(doc).quality_status === 'REQUIRE_INDIVIDUAL_REVIEW' || (String(doc.title || '').toLowerCase().includes('smartlogger') && Number(doc.chunk_count || 0) >= 100)
}

function approvalEligible(doc: Record<string, unknown>) {
  return !isVendorOfficial(doc) || !requiresIndividualReview(doc)
}

function formatDateTime(value: unknown) {
  if (!value) return '-'
  const parsed = new Date(String(value))
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString('zh-CN', { hour12: false })
}

function sourceDomain(doc: Record<string, unknown>) {
  try { return new URL(String(doc.source || '')).hostname } catch { return '-' }
}

function alarmCount(doc: Record<string, unknown>) {
  const alarm = metadata(doc).alarm_knowledge || {}
  return (alarm.explicit_alarm_codes || []).length + (alarm.named_alarms || []).length
}

function locatorText(doc: Record<string, unknown>) {
  const locator = metadata(doc).section_locator || {}
  return [locator.nid, locator.part_no, locator.question_title, locator.section_title].filter(Boolean).join(' / ') || '-'
}

onMounted(loadDocuments)
</script>
