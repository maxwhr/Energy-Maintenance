<template>
  <PageFrame
    title="一线经验"
    code="KNOWLEDGE / CONTRIBUTIONS"
    description="工程师提交华为与阳光电源光伏逆变器现场检修经验，专家审核后可转换为可追溯知识文档与知识切片。"
  >
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadPageData">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
      {{ error }}
    </div>

    <div class="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
      <DataPanel v-if="canCreate" :title="editingId ? '编辑经验草稿' : '提交一线经验'" subtitle="内容会先保存为草稿，提交审核后由专家确认是否入库。">
        <form class="grid gap-3" @submit.prevent="saveDraft">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            标题
            <input v-model.trim="form.title" class="scada-input" required placeholder="例如：SUN2000 低绝缘阻抗现场排查经验" />
          </label>
          <div class="grid gap-3 md:grid-cols-2">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              厂家
              <select v-model="form.manufacturer" class="scada-input">
                <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              产品系列
              <select v-model="form.product_series" class="scada-input">
                <option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </div>
          <div class="grid gap-3 md:grid-cols-2">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              贡献类型
              <select v-model="form.contribution_type" class="scada-input">
                <option v-for="item in contributionTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              故障类型
              <select v-model="form.fault_type" class="scada-input">
                <option value="">未指定</option>
                <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </div>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            告警代码
            <input v-model.trim="form.alarm_code" class="scada-input" placeholder="例如 LOW-INS / COMM-001" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            关联设备
            <select v-model="form.device_id" class="scada-input">
              <option value="">不绑定设备</option>
              <option v-for="device in devices" :key="device.id" :value="device.id">
                {{ device.device_name }} / {{ labelOf(device.manufacturer, manufacturerOptions) }} / {{ device.product_series || '-' }}
              </option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            关联诊断记录
            <select v-model="form.related_diagnosis_trace_id" class="scada-input">
              <option value="">不绑定诊断记录</option>
              <option v-for="item in diagnosisRecords" :key="item.record_id" :value="item.trace_id || ''">
                {{ item.title }} / {{ item.trace_id || '-' }}
              </option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            关联检修任务
            <select v-model="form.related_task_id" class="scada-input">
              <option value="">不绑定任务</option>
              <option v-for="task in tasks" :key="task.id" :value="task.id">
                {{ task.title }} / {{ task.device_name || '-' }}
              </option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            关联问答记录
            <select v-model="form.qa_trace_id" class="scada-input">
              <option value="">不绑定问答记录</option>
              <option v-for="item in qaRecords" :key="item.record_id" :value="item.trace_id || ''">
                {{ item.title }} / {{ item.trace_id || '-' }}
              </option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            故障现象
            <textarea v-model.trim="form.symptom_description" class="scada-input min-h-20" placeholder="描述现场现象、告警信息、发生条件。" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            处理过程
            <textarea v-model.trim="form.diagnosis_process" class="scada-input min-h-24" placeholder="记录排查步骤、测量值、现场判断过程。" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            原因判断
            <textarea v-model.trim="form.root_cause" class="scada-input min-h-20" placeholder="说明最终定位或暂定原因。" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            处理措施
            <textarea v-model.trim="form.solution" class="scada-input min-h-20" placeholder="说明恢复措施、替换部件、复检结果。" />
          </label>
          <div class="grid gap-3 md:grid-cols-3">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              工具清单
              <textarea v-model.trim="form.tools_text" class="scada-input min-h-20" placeholder="每行一个工具" />
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              更换部件
              <textarea v-model.trim="form.parts_text" class="scada-input min-h-20" placeholder="每行一个部件" />
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              安全注意事项
              <textarea v-model.trim="form.safety_text" class="scada-input min-h-20" placeholder="每行一条安全要求" />
            </label>
          </div>
          <MediaEvidencePicker
            v-model="form.media_ids"
            title="关联现场图片证据"
            :device-id="form.device_id || ''"
            :manufacturer="form.manufacturer"
            :product-series="form.product_series"
            :fault-type="form.fault_type"
            :alarm-code="form.alarm_code"
            :task-id="form.related_task_id || ''"
          />
          <div class="flex flex-wrap gap-2">
            <button class="scada-button primary" type="submit" :disabled="saving">
              <Save :size="16" />
              {{ saving ? '保存中' : '保存草稿' }}
            </button>
            <button v-if="editingId" class="scada-button" type="button" @click="resetForm">
              <X :size="16" />
              取消编辑
            </button>
          </div>
        </form>
      </DataPanel>

      <DataPanel title="经验列表" subtitle="草稿、提交审核、专家处理和入库状态均来自后端 PostgreSQL。">
        <div class="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[150px_150px_150px_minmax(0,1fr)_auto]">
          <select v-model="filters.review_status" class="scada-input">
            <option value="">全部状态</option>
            <option v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.manufacturer" class="scada-input">
            <option value="">全部厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.contribution_type" class="scada-input">
            <option value="">全部类型</option>
            <option v-for="item in contributionTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索标题、内容、trace_id" />
          <button class="scada-button" type="button" :disabled="loading" @click="loadContributions">
            <Search :size="16" />
            查询
          </button>
        </div>

        <div v-if="contributions.length" class="space-y-3">
          <article
            v-for="item in contributions"
            :key="item.id"
            class="rounded-md border border-slate-600/20 bg-black/20 p-4"
          >
            <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <h3 class="font-black text-white">{{ item.title }}</h3>
                  <StatusPill :value="item.review_status" />
                </div>
                <p class="mt-2 line-clamp-3 text-sm leading-7 text-slate-300">
                  {{ item.content_preview || item.content || '暂无内容摘要' }}
                </p>
                <div class="mt-2 flex flex-wrap gap-3 text-xs text-slate-400">
                  <span>{{ labelOf(item.manufacturer, manufacturerOptions) }}</span>
                  <span>{{ item.product_series || '-' }}</span>
                  <span>{{ formatContributionTypeLabel(item.contribution_type) }}</span>
                  <span>提交人：{{ item.submitted_by_name || '-' }}</span>
                  <span>{{ formatTime(item.updated_at) }}</span>
                </div>
                <div v-if="item.review_comment" class="mt-2 text-xs text-amber-200">
                  审核意见：{{ item.review_comment }}
                </div>
              </div>
              <div class="flex shrink-0 flex-wrap gap-2">
                <button class="scada-button !min-h-8 !px-3" type="button" @click="openDetail(item.id)">
                  <FileSearch :size="15" />
                  详情
                </button>
                <button v-if="canEditContribution(item)" class="scada-button !min-h-8 !px-3" type="button" @click="editContribution(item.id)">
                  <Pencil :size="15" />
                  编辑
                </button>
                <button v-if="canSubmitContribution(item)" class="scada-button primary !min-h-8 !px-3" type="button" @click="submitContribution(item.id)">
                  <Send :size="15" />
                  提交审核
                </button>
                <button v-if="canReviewContribution(item)" class="scada-button !min-h-8 !px-3" type="button" @click="requestChanges(item.id)">
                  <MessageSquareWarning :size="15" />
                  要求修改
                </button>
                <button v-if="canReviewContribution(item)" class="scada-button primary !min-h-8 !px-3" type="button" @click="approveContribution(item.id)">
                  <CheckCircle2 :size="15" />
                  通过
                </button>
                <button v-if="canReviewContribution(item)" class="scada-button danger !min-h-8 !px-3" type="button" @click="rejectContribution(item.id)">
                  <Ban :size="15" />
                  驳回
                </button>
                <button v-if="canConvertContribution(item)" class="scada-button primary !min-h-8 !px-3" type="button" @click="convertContribution(item.id)">
                  <FilePlus2 :size="15" />
                  转为知识
                </button>
                <button v-if="canArchiveContribution(item)" class="scada-button !min-h-8 !px-3" type="button" @click="archiveContribution(item.id)">
                  <Archive :size="15" />
                  归档
                </button>
              </div>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无一线经验记录" />
      </DataPanel>
    </div>

    <DataPanel v-if="selected" title="经验详情" subtitle="审核历史、来源 trace_id、关联图片和转换后的知识文档均保留追溯信息。">
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <InfoItem label="状态" :value="formatStatusLabel(selected.review_status)" />
        <InfoItem label="厂家" :value="labelOf(selected.manufacturer, manufacturerOptions)" />
        <InfoItem label="产品系列" :value="selected.product_series || '-'" />
        <InfoItem label="贡献类型" :value="formatContributionTypeLabel(selected.contribution_type)" />
        <InfoItem label="设备" :value="selected.device_name || '-'" />
        <InfoItem label="故障类型" :value="labelOf(selected.fault_type, faultTypeOptions)" />
        <InfoItem label="告警代码" :value="selected.alarm_code || '-'" />
        <InfoItem label="trace_id" :value="selected.source_trace_id || '-'" />
      </div>
      <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">{{ selected.title }}</h3>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200">{{ selected.content }}</p>
          <div v-if="selected.approved_document_id" class="mt-3 rounded-md border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-xs text-emerald-200">
            已转换知识文档：{{ selected.approved_document_title || selected.approved_document_id }}
          </div>
        </section>
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">审核记录</h3>
          <div v-if="reviewRecords.length" class="mt-3 space-y-2">
            <article v-for="record in reviewRecords" :key="String(record.id)" class="rounded-md bg-white/[0.03] p-3 text-xs text-slate-300">
              <div class="font-bold text-white">{{ actionLabel(String(record.review_action || '-')) }}</div>
              <div class="mt-1 text-slate-400">
                {{ record.before_status || '-' }} → {{ record.after_status || '-' }} / {{ formatTime(String(record.reviewed_at || '')) }}
              </div>
              <p v-if="record.review_comment" class="mt-1 leading-5">{{ record.review_comment }}</p>
            </article>
          </div>
          <EmptyState v-else text="暂无审核记录" />
        </section>
      </div>
      <section class="mt-4">
        <MediaEvidencePicker
          v-model="selectedMediaIds"
          title="关联现场图片证据"
          :device-id="selected.device_id || ''"
          :manufacturer="selected.manufacturer || ''"
          :product-series="selected.product_series || ''"
          :fault-type="selected.fault_type || ''"
          :alarm-code="selected.alarm_code || ''"
          readonly
        />
      </section>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref, watch } from 'vue'
import {
  Archive,
  Ban,
  CheckCircle2,
  FilePlus2,
  FileSearch,
  MessageSquareWarning,
  Pencil,
  RefreshCcw,
  Save,
  Search,
  Send,
  X
} from '@lucide/vue'
import {
  approveKnowledgeContributionApi,
  archiveKnowledgeContributionApi,
  convertKnowledgeContributionApi,
  createKnowledgeContributionApi,
  getDevicesApi,
  getKnowledgeContributionApi,
  getKnowledgeContributionsApi,
  getWorkordersApi,
  rejectKnowledgeContributionApi,
  requestContributionChangesApi,
  searchRecordCenterApi,
  submitKnowledgeContributionApi,
  updateKnowledgeContributionApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidencePicker from '@/components/MediaEvidencePicker.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useUserStore } from '@/stores/user'
import {
  contributionTypeOptions,
  faultTypeOptions,
  manufacturerOptions,
  productSeriesOptions
} from '@/types'
import type {
  DeviceItem,
  KnowledgeContribution,
  KnowledgeContributionPayload,
  MaintenanceTask,
  RecordCenterItem
} from '@/types'
import { formatContributionTypeLabel, formatStatusLabel } from '@/utils/display'

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

const userStore = useUserStore()
const contributions = ref<KnowledgeContribution[]>([])
const selected = ref<KnowledgeContribution | null>(null)
const devices = ref<DeviceItem[]>([])
const tasks = ref<MaintenanceTask[]>([])
const diagnosisRecords = ref<RecordCenterItem[]>([])
const qaRecords = ref<RecordCenterItem[]>([])
const editingId = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')

const filters = reactive({
  review_status: '',
  manufacturer: '',
  contribution_type: '',
  keyword: ''
})

const form = reactive({
  title: '',
  contribution_type: 'maintenance_experience',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  device_type: 'pv_inverter',
  device_id: '',
  fault_type: '',
  alarm_code: '',
  related_diagnosis_trace_id: '',
  related_task_id: '',
  qa_trace_id: '',
  symptom_description: '',
  diagnosis_process: '',
  root_cause: '',
  solution: '',
  tools_text: '',
  parts_text: '',
  safety_text: '',
  media_ids: [] as string[]
})

const statusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '已提交', value: 'submitted' },
  { label: '需修改', value: 'changes_requested' },
  { label: '已通过', value: 'approved' },
  { label: '已入库', value: 'converted' },
  { label: '已驳回', value: 'rejected' },
  { label: '已归档', value: 'archived' }
]

const canCreate = computed(() => userStore.role !== 'viewer')
const canReview = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const currentUserId = computed(() => userStore.user?.id || '')
const seriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === form.manufacturer))
const selectedMediaIds = computed({
  get: () => selected.value?.media_ids ?? [],
  set: (_value: string[]) => {
    // Detail mode is readonly; keep v-model compatible with MediaEvidencePicker.
  }
})
const reviewRecords = computed(() => selected.value?.review_records ?? [])

watch(
  () => form.manufacturer,
  () => {
    const valid = seriesOptions.value.some((item) => item.value === form.product_series)
    if (!valid) form.product_series = seriesOptions.value[0]?.value ?? ''
  }
)

async function loadPageData() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadContributions(), loadDevices(), loadTasks(), loadTraceRecords()])
  } catch (err) {
    error.value = err instanceof Error ? err.message : '一线经验数据读取失败'
  } finally {
    loading.value = false
  }
}

async function loadContributions() {
  const params: Record<string, string | number> = { page: 1, page_size: 50 }
  if (filters.review_status) params.review_status = filters.review_status
  if (filters.manufacturer) params.manufacturer = filters.manufacturer
  if (filters.contribution_type) params.contribution_type = filters.contribution_type
  if (filters.keyword) params.keyword = filters.keyword
  const result = await getKnowledgeContributionsApi(params)
  contributions.value = result.items
}

async function loadDevices() {
  try {
    const result = await getDevicesApi({ page: 1, page_size: 100, device_type: 'pv_inverter' })
    devices.value = result.items
  } catch {
    devices.value = []
  }
}

async function loadTasks() {
  try {
    const result = await getWorkordersApi({ page: 1, page_size: 100, device_type: 'pv_inverter' })
    tasks.value = result.items
  } catch {
    tasks.value = []
  }
}

async function loadTraceRecords() {
  try {
    const [diagnosis, qa] = await Promise.all([
      searchRecordCenterApi({ record_type: 'diagnosis', page: 1, page_size: 50 }),
      searchRecordCenterApi({ record_type: 'qa', page: 1, page_size: 50 })
    ])
    diagnosisRecords.value = diagnosis.items.filter((item) => !!item.trace_id)
    qaRecords.value = qa.items.filter((item) => !!item.trace_id)
  } catch {
    diagnosisRecords.value = []
    qaRecords.value = []
  }
}

async function saveDraft() {
  error.value = ''
  if (!form.title.trim()) {
    error.value = '请填写经验标题'
    return
  }
  saving.value = true
  try {
    const payload = buildPayload()
    const result = editingId.value
      ? await updateKnowledgeContributionApi(editingId.value, payload)
      : await createKnowledgeContributionApi(payload)
    selected.value = result
    editingId.value = result.id
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: '一线经验草稿已保存' } }))
    await loadContributions()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '一线经验保存失败'
  } finally {
    saving.value = false
  }
}

function buildPayload(): KnowledgeContributionPayload {
  return {
    title: form.title,
    contribution_type: form.contribution_type,
    manufacturer: form.manufacturer,
    product_series: form.product_series,
    device_type: form.device_type,
    device_id: form.device_id || null,
    source_trace_id: form.related_diagnosis_trace_id || form.qa_trace_id || null,
    fault_type: form.fault_type || null,
    alarm_code: form.alarm_code || null,
    symptom_description: form.symptom_description || null,
    diagnosis_process: form.diagnosis_process || null,
    root_cause: form.root_cause || null,
    solution: form.solution || null,
    tools_used: lines(form.tools_text),
    parts_used: lines(form.parts_text),
    safety_notes: lines(form.safety_text),
    media_ids: form.media_ids,
    related_diagnosis_trace_id: form.related_diagnosis_trace_id || null,
    related_task_id: form.related_task_id || null,
    qa_trace_id: form.qa_trace_id || null
  }
}

async function openDetail(id: string) {
  error.value = ''
  try {
    selected.value = await getKnowledgeContributionApi(id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '一线经验详情读取失败'
  }
}

async function editContribution(id: string) {
  await openDetail(id)
  if (!selected.value) return
  editingId.value = selected.value.id
  form.title = selected.value.title
  form.contribution_type = selected.value.contribution_type
  form.manufacturer = selected.value.manufacturer || 'huawei'
  form.product_series = selected.value.product_series || seriesOptions.value[0]?.value || 'SUN2000'
  form.device_type = selected.value.device_type || 'pv_inverter'
  form.device_id = selected.value.device_id || ''
  form.fault_type = selected.value.fault_type || ''
  form.alarm_code = selected.value.alarm_code || ''
  form.related_diagnosis_trace_id = selected.value.related_diagnosis_trace_id || ''
  form.related_task_id = selected.value.related_task_id || ''
  form.qa_trace_id = selected.value.qa_trace_id || ''
  form.symptom_description = selected.value.symptom_description || ''
  form.diagnosis_process = selected.value.diagnosis_process || ''
  form.root_cause = selected.value.root_cause || ''
  form.solution = selected.value.solution || ''
  form.tools_text = (selected.value.tools_used || []).join('\n')
  form.parts_text = (selected.value.parts_used || []).join('\n')
  form.safety_text = (selected.value.safety_notes || []).join('\n')
  form.media_ids = [...(selected.value.media_ids || [])]
}

function resetForm() {
  editingId.value = ''
  form.title = ''
  form.contribution_type = 'maintenance_experience'
  form.manufacturer = 'huawei'
  form.product_series = 'SUN2000'
  form.device_type = 'pv_inverter'
  form.device_id = ''
  form.fault_type = ''
  form.alarm_code = ''
  form.related_diagnosis_trace_id = ''
  form.related_task_id = ''
  form.qa_trace_id = ''
  form.symptom_description = ''
  form.diagnosis_process = ''
  form.root_cause = ''
  form.solution = ''
  form.tools_text = ''
  form.parts_text = ''
  form.safety_text = ''
  form.media_ids = []
}

async function submitContribution(id: string) {
  if (!window.confirm('确认提交给专家审核？提交后需退回修改才可继续编辑。')) return
  await runAction(() => submitKnowledgeContributionApi(id), '已提交审核')
}

async function requestChanges(id: string) {
  const comment = window.prompt('请输入修改意见')
  if (comment === null) return
  await runAction(() => requestContributionChangesApi(id, comment), '已退回修改')
}

async function approveContribution(id: string) {
  const comment = window.prompt('审核通过意见（可选）') ?? ''
  await runAction(() => approveKnowledgeContributionApi(id, comment), '已审核通过')
}

async function rejectContribution(id: string) {
  const comment = window.prompt('请输入驳回原因')
  if (comment === null) return
  await runAction(() => rejectKnowledgeContributionApi(id, comment), '已驳回')
}

async function convertContribution(id: string) {
  const comment = window.prompt('入库说明（可选）') ?? ''
  await runAction(() => convertKnowledgeContributionApi(id, comment), '已转换为知识文档并生成切片')
}

async function archiveContribution(id: string) {
  if (!window.confirm('确认归档该经验？')) return
  await runAction(() => archiveKnowledgeContributionApi(id, 'Archived from contribution page'), '已归档')
}

async function runAction(action: () => Promise<unknown>, message: string) {
  error.value = ''
  try {
    await action()
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
    await loadContributions()
    if (selected.value) await openDetail(selected.value.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '操作失败'
  }
}

function canEditContribution(item: KnowledgeContribution) {
  if (canReview.value && item.review_status !== 'converted') return true
  return item.submitted_by === currentUserId.value && ['draft', 'changes_requested', 'rejected'].includes(item.review_status)
}

function canSubmitContribution(item: KnowledgeContribution) {
  return item.submitted_by === currentUserId.value && ['draft', 'changes_requested', 'rejected'].includes(item.review_status)
}

function canReviewContribution(item: KnowledgeContribution) {
  return canReview.value && ['submitted', 'pending_review'].includes(item.review_status)
}

function canConvertContribution(item: KnowledgeContribution) {
  return canReview.value && item.review_status === 'approved' && !item.approved_document_id
}

function canArchiveContribution(item: KnowledgeContribution) {
  if (['converted', 'archived'].includes(item.review_status)) return false
  return canReview.value || item.submitted_by === currentUserId.value
}

function lines(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function labelOf(value: string | null | undefined, options: Array<{ label: string; value: string }>) {
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

function actionLabel(value: string) {
  const labels: Record<string, string> = {
    create: '创建草稿',
    update: '更新草稿',
    submit: '提交审核',
    request_changes: '要求修改',
    approve: '审核通过',
    reject: '驳回',
    convert_to_document: '转换入库',
    archive: '归档'
  }
  return labels[value] ?? value
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

onMounted(loadPageData)
</script>
