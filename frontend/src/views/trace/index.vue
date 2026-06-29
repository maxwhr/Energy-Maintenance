<template>
  <PageFrame title="记录追溯" code="RECORD / TRACE" description="按 trace_id、设备、故障类型串联问答、诊断、任务和检修记录。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadData">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 lg:grid-cols-4">
      <DataPanel v-for="item in overviewCards" :key="item.label" :title="item.label">
        <div class="text-2xl font-black text-white">{{ item.value }}</div>
        <div class="mt-1 text-xs text-slate-400">{{ item.detail }}</div>
      </DataPanel>
    </div>

    <DataPanel title="追溯查询">
      <form class="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[150px_1fr_150px_150px_auto]" @submit.prevent="search">
        <select v-model="filters.record_type" class="scada-input">
          <option value="all">全部记录</option>
          <option value="qa">问答记录</option>
          <option value="diagnosis">诊断记录</option>
          <option value="task">检修任务</option>
          <option value="maintenance_record">检修记录</option>
          <option value="sop_execution">SOP 执行</option>
          <option value="knowledge_document">知识文档</option>
          <option value="knowledge_contribution">一线经验</option>
          <option value="media">媒体资料</option>
        </select>
        <input v-model.trim="filters.keyword" class="scada-input" placeholder="标题、摘要、告警代码或 trace_id" />
        <input v-model.trim="filters.trace_id" class="scada-input" placeholder="trace_id" />
        <select v-model="filters.manufacturer" class="scada-input">
          <option value="">不限厂家</option>
          <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <button class="scada-button primary" type="submit" :disabled="searching">
          <Search :size="16" />
          {{ searching ? '查询中' : '查询' }}
        </button>
      </form>

      <div v-if="records.length" class="space-y-3">
        <article v-for="record in records" :key="`${record.record_type}-${record.record_id}`" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div class="min-w-0">
              <div class="font-black text-white">{{ record.title || recordTypeLabel(record.record_type) }}</div>
              <p class="mt-2 line-clamp-3 text-sm leading-7 text-slate-300">{{ record.summary || '暂无摘要' }}</p>
              <div class="mt-2 flex flex-wrap gap-3 text-xs text-slate-400">
                <span>类型：{{ recordTypeLabel(record.record_type) }}</span>
                <span>设备：{{ record.device_name || '-' }}</span>
                <span>trace_id：{{ record.trace_id || '-' }}</span>
                <span>{{ formatTime(record.created_at) }}</span>
              </div>
            </div>
            <div class="flex shrink-0 flex-wrap items-center gap-2">
              <StatusPill :value="record.status || 'info'" />
              <button class="scada-button !min-h-8 !px-3" type="button" @click="viewDetail(record.record_type, record.record_id)">
                <FileSearch :size="15" />
                查看详情
              </button>
              <button v-if="record.device_id" class="scada-button !min-h-8 !px-3" type="button" @click="openTimeline(record.device_id)">
                <History :size="15" />
                设备时间线
              </button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无追溯记录" />
    </DataPanel>

    <DataPanel title="设备时间线入口" subtitle="设备来自当前检索结果，不需要手工输入 UUID。">
      <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
        <select v-model="selectedDeviceId" class="scada-input">
          <option value="">请选择当前结果中的设备</option>
          <option v-for="device in availableDevices" :key="device.id" :value="device.id">{{ device.name }}</option>
        </select>
        <button class="scada-button" type="button" :disabled="!selectedDeviceId || timelineLoading" @click="openSelectedTimeline">
          <History :size="16" />
          查看设备时间线
        </button>
      </div>
    </DataPanel>

    <DataPanel v-if="detail" title="记录详情" subtitle="主要业务字段采用结构化展示，原始字段仅保留在折叠区。">
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <InfoItem label="记录类型" :value="recordTypeLabel(detail.record_type)" />
        <InfoItem label="标题" :value="detailSummary.title || '-'" />
        <InfoItem label="状态" :value="formatStatusLabel(detailSummary.status)" />
        <InfoItem label="创建时间" :value="formatTime(detailSummary.created_at)" />
        <InfoItem label="设备" :value="detailSummary.device_name || detailDeviceName || '-'" />
        <InfoItem label="故障类型" :value="labelOf(detailSummary.fault_type)" />
        <InfoItem label="告警代码" :value="detailSummary.alarm_code || '-'" />
        <InfoItem label="操作人" :value="detailSummary.created_by_name || '-'" />
      </div>

      <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">摘要</h3>
          <p class="mt-2 whitespace-pre-wrap text-sm leading-7 text-slate-300">{{ detailSummary.summary || recordSummary || '暂无摘要' }}</p>
          <div class="mt-3 break-all font-mono text-xs text-slate-400">trace_id: {{ detailSummary.trace_id || recordTraceId || '-' }}</div>
        </section>
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">设备追溯</h3>
          <p class="mt-2 text-sm leading-6 text-slate-300">{{ detailSummary.device_name || detailDeviceName || '该记录未关联设备' }}</p>
          <button v-if="detailDeviceId" class="scada-button mt-3 w-full" type="button" @click="openTimeline(detailDeviceId)">
            <History :size="16" />
            查看设备时间线
          </button>
        </section>
      </div>

      <section v-if="detailMediaItems.length" class="mt-4">
        <h3 class="mb-2 text-sm font-black text-white">关联图片证据</h3>
        <p class="mb-3 text-xs leading-5 text-slate-400">图片来自诊断、问答或任务关联；如存在 OCR 文本，仅作为机器识别参考，不代表图像故障识别结论。</p>
        <MediaEvidenceGallery :items="detailMediaItems" />
      </section>

      <section class="mt-4">
        <h3 class="mb-2 text-sm font-black text-white">知识图谱关联</h3>
        <div v-if="kgTrace.has_context" class="grid gap-3 lg:grid-cols-2">
          <article v-for="(summary, index) in kgTrace.summaries" :key="index" class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3 text-sm text-slate-200">
            <div class="text-xs font-bold text-cyan-100">图谱摘要 {{ index + 1 }}</div>
            <div class="mt-2 flex flex-wrap gap-2">
              <span v-for="node in summary.matched_nodes || []" :key="String(node.id)" class="rounded bg-black/20 px-2 py-1 text-xs">
                {{ node.display_name || node.id }}
              </span>
            </div>
            <p class="mt-2 text-xs text-slate-400">证据数量：{{ summary.evidence_count ?? 0 }}</p>
          </article>
          <article v-for="item in kgTrace.evidence" :key="String(item.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
            <div class="text-xs font-bold text-cyan-100">{{ item.source_type }}</div>
            <p class="mt-2 leading-6">{{ item.evidence_text || '暂无证据文本' }}</p>
            <p class="mt-2 break-all font-mono text-xs text-slate-500">{{ item.chunk_id || item.document_id || item.source_id || item.id }}</p>
          </article>
        </div>
        <EmptyState v-else text="该记录暂无图谱关联。" />
      </section>

      <section class="mt-4">
        <h3 class="mb-2 text-sm font-black text-white">关联记录</h3>
        <div v-if="detail.related_records.length" class="space-y-2">
          <article v-for="item in detail.related_records" :key="`${item.record_type}-${item.record_id}`" class="flex flex-col gap-3 rounded-md border border-slate-600/20 bg-black/20 p-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div class="text-sm font-bold text-white">{{ item.title }}</div>
              <div class="mt-1 text-xs text-slate-400">{{ recordTypeLabel(item.record_type) }} / {{ formatTime(item.created_at) }} / {{ item.trace_id || '-' }}</div>
            </div>
            <button class="scada-button !min-h-8 !px-3" type="button" @click="viewDetail(item.record_type, item.record_id)">查看详情</button>
          </article>
        </div>
        <EmptyState v-else text="暂无关联记录" />
      </section>

      <details class="mt-4 rounded-md border border-slate-600/20 bg-black/20 p-4">
        <summary class="cursor-pointer text-sm font-black text-white">技术字段（可选）</summary>
        <pre class="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs leading-6 text-slate-400">{{ technicalJson }}</pre>
      </details>
    </DataPanel>

    <DataPanel v-if="timeline" title="设备时间线" :subtitle="timelineDeviceTitle">
      <div v-if="timeline.timeline.length" class="relative space-y-3 border-l border-cyan-300/30 pl-5">
        <article v-for="item in timeline.timeline" :key="`${item.record_type}-${item.record_id}`" class="relative rounded-md border border-slate-600/20 bg-black/20 p-4">
          <span class="absolute -left-[27px] top-5 h-3 w-3 rounded-full border-2 border-cyan-200 bg-[#195FA8]"></span>
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <div class="font-black text-white">{{ item.title }}</div>
              <p class="mt-2 text-sm leading-6 text-slate-300">{{ item.summary || '暂无摘要' }}</p>
              <div class="mt-2 flex flex-wrap gap-3 text-xs text-slate-400">
                <span>{{ formatTime(item.time) }}</span>
                <span>{{ recordTypeLabel(item.record_type) }}</span>
                <span>trace_id: {{ item.trace_id || '-' }}</span>
                <span>操作人：{{ item.operator_name || '-' }}</span>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <StatusPill :value="item.status || 'info'" />
              <button class="scada-button !min-h-8 !px-3" type="button" @click="viewDetail(item.record_type, item.record_id)">查看详情</button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="该设备暂无时间线记录" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { FileSearch, History, RefreshCcw, Search } from '@lucide/vue'
import {
  getDeviceTimelineApi,
  getRecordCenterOverviewApi,
  getRecordDetailApi,
  searchRecordCenterApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { faultTypeOptions, manufacturerOptions } from '@/types'
import { formatRecordTypeLabel, formatStatusLabel } from '@/utils/display'
import type {
  DeviceTimelineResponse,
  MediaContextItem,
  RecordCenterDetail,
  RecordCenterItem,
  RecordCenterOverview
} from '@/types'

interface KgTraceSummary {
  matched_nodes?: Array<{ id?: string; display_name?: string }>
  evidence_count?: number
}

interface KgTraceEvidence {
  id?: string
  source_type?: string
  source_id?: string | null
  document_id?: string | null
  chunk_id?: string | null
  evidence_text?: string | null
}

const InfoItem = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true }
  },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-md bg-white/[0.03] p-3' }, [
        h('div', { class: 'text-xs font-bold text-slate-400' }, props.label),
        h('div', { class: 'mt-1 break-words text-sm font-black text-white' }, props.value)
      ])
  }
})

const overview = ref<RecordCenterOverview | null>(null)
const records = ref<RecordCenterItem[]>([])
const detail = ref<RecordCenterDetail | null>(null)
const timeline = ref<DeviceTimelineResponse | null>(null)
const selectedDeviceId = ref('')
const loading = ref(false)
const searching = ref(false)
const timelineLoading = ref(false)
const error = ref('')
const filters = reactive({ record_type: 'all', keyword: '', trace_id: '', manufacturer: '' })

const overviewCards = computed(() => {
  const current = overview.value
  const totals = current?.totals ?? {}
  return [
    { label: '问答记录', value: current?.qa_records ?? totals.qa_records ?? totals.qa ?? 0, detail: 'qa_records' },
    { label: '诊断记录', value: current?.diagnosis_records ?? totals.diagnosis_records ?? totals.diagnosis ?? 0, detail: 'diagnosis_records' },
    { label: '检修任务', value: current?.maintenance_tasks ?? totals.maintenance_tasks ?? totals.tasks ?? 0, detail: 'maintenance_tasks' },
    { label: '检修记录', value: current?.maintenance_records ?? totals.maintenance_records ?? 0, detail: 'device_maintenance_records' },
    { label: '一线经验', value: current?.knowledge_contributions ?? totals.knowledge_contributions ?? 0, detail: 'knowledge_contributions' }
  ]
})
const availableDevices = computed(() => {
  const unique = new Map<string, string>()
  records.value.forEach((record) => {
    if (record.device_id) unique.set(record.device_id, record.device_name || record.device_id)
  })
  return Array.from(unique, ([id, name]) => ({ id, name }))
})
const detailSummary = computed<RecordCenterItem>(() => {
  if (detail.value?.summary_item) return detail.value.summary_item
  const record = detail.value?.record ?? {}
  return {
    record_type: detail.value?.record_type || '',
    record_id: detail.value?.record_id || '',
    title: String(record.title || record.question || record.fault_description || '记录详情'),
    summary: String(record.summary || record.answer || record.diagnosis_summary || record.fault_description || ''),
    device_id: stringValue(record.device_id),
    device_name: stringValue(record.device_name),
    status: stringValue(record.status || record.task_status),
    fault_type: stringValue(record.fault_type),
    alarm_code: stringValue(record.alarm_code),
    trace_id: stringValue(record.trace_id || record.source_trace_id),
    created_at: stringValue(record.created_at)
  }
})
const detailDeviceId = computed(() => detailSummary.value.device_id || stringValue(detail.value?.record.device_id) || '')
const detailDeviceName = computed(() => stringValue(detail.value?.record.device_name) || '')
const recordSummary = computed(() => {
  const record = detail.value?.record ?? {}
  return stringValue(record.summary || record.answer || record.diagnosis_summary || record.fault_description || record.repair_action) || ''
})
const recordTraceId = computed(() => stringValue(detail.value?.record.trace_id || detail.value?.record.source_trace_id) || '')
const technicalJson = computed(() => JSON.stringify(detail.value?.record ?? {}, null, 2))
const detailMediaItems = computed(
  () => ((detail.value?.record.media_items as MediaContextItem[] | undefined) ?? [])
)
const kgTrace = computed(() => {
  const value = (detail.value?.record.knowledge_graph || {}) as {
    has_context?: boolean
    summaries?: KgTraceSummary[]
    evidence?: KgTraceEvidence[]
  }
  return {
    has_context: Boolean(value.has_context),
    summaries: value.summaries || [],
    evidence: value.evidence || []
  }
})
const timelineDeviceTitle = computed(() => {
  const device = timeline.value?.device ?? {}
  return String(device.device_name || device.name || device.device_code || '已关联设备')
})

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    overview.value = await getRecordCenterOverviewApi()
    await search()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '追溯数据读取失败'
  } finally {
    loading.value = false
  }
}

async function search() {
  searching.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 30, record_type: filters.record_type }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.trace_id) params.trace_id = filters.trace_id
    if (filters.manufacturer) params.manufacturer = filters.manufacturer
    const result = await searchRecordCenterApi(params)
    records.value = result.items
    if (selectedDeviceId.value && !availableDevices.value.some((item) => item.id === selectedDeviceId.value)) {
      selectedDeviceId.value = ''
    }
  } catch (err) {
    records.value = []
    error.value = err instanceof Error ? err.message : '追溯记录查询失败'
  } finally {
    searching.value = false
  }
}

async function viewDetail(recordType: string, recordId: string) {
  error.value = ''
  try {
    detail.value = await getRecordDetailApi(recordType, recordId)
  } catch (err) {
    detail.value = null
    error.value = err instanceof Error ? err.message : '记录详情读取失败'
  }
}

async function openTimeline(deviceId: string) {
  timelineLoading.value = true
  error.value = ''
  try {
    selectedDeviceId.value = deviceId
    timeline.value = await getDeviceTimelineApi(deviceId)
  } catch (err) {
    timeline.value = null
    error.value = err instanceof Error ? err.message : '设备时间线读取失败'
  } finally {
    timelineLoading.value = false
  }
}

async function openSelectedTimeline() {
  if (selectedDeviceId.value) await openTimeline(selectedDeviceId.value)
}

function recordTypeLabel(value?: string | null) {
  return formatRecordTypeLabel(value)
}

function labelOf(value?: string | null) {
  return faultTypeOptions.find((item) => item.value === value)?.label ?? value ?? '-'
}

function stringValue(value: unknown) {
  return value == null ? undefined : String(value)
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

onMounted(loadData)
</script>
