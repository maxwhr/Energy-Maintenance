<template>
  <PageFrame title="作业规程" code="SOP / WORKFLOW" description="管理光伏逆变器检修规程模板，并按故障类型生成和执行作业步骤。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadAll">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="生成规程建议">
        <form class="grid gap-3" @submit.prevent="generate">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            关联诊断记录
            <select v-model="generateForm.diagnosis_trace_id" class="scada-input">
              <option value="">不关联诊断</option>
              <option v-for="record in diagnosisRecords" :key="String(record.trace_id)" :value="String(record.trace_id)">
                {{ String(record.fault_description || record.trace_id) }} / {{ String(record.device_name || '-') }}
              </option>
            </select>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              厂家
              <select v-model="generateForm.manufacturer" class="scada-input">
                <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              产品系列
              <select v-model="generateForm.product_series" class="scada-input">
                <option v-for="item in seriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </div>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            故障类型
            <select v-model="generateForm.fault_type" class="scada-input">
              <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            告警代码
            <input v-model.trim="generateForm.alarm_code" class="scada-input" />
          </label>
          <label class="flex items-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-sm font-bold text-cyan-100">
            <input v-model="generateForm.enable_kg_enhancement" type="checkbox" />
            启用知识图谱增强
          </label>
          <button class="scada-button primary" type="submit" :disabled="generating">
            <ClipboardCheck :size="16" />
            {{ generating ? '生成中' : '生成规程建议' }}
          </button>
        </form>
      </DataPanel>

      <DataPanel title="生成结果">
        <div v-if="generated" class="space-y-4">
          <div class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div class="text-lg font-black text-white">{{ generated.title }}</div>
            <div class="mt-1 text-xs text-cyan-200">
              来源：{{ formatProviderName(generated.source) }}
              <span v-if="formatProviderName(generated.source) !== generated.source">（{{ generated.source }}）</span>
              / 置信度（confidence）{{ Math.round(generated.confidence * 100) }}%
            </div>
          </div>
          <section>
            <h3 class="mb-2 text-sm font-black text-white">步骤</h3>
            <div class="space-y-2">
              <article v-for="(step, index) in generated.steps" :key="index" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
                <div class="text-sm font-black text-white">{{ stepTitle(step, index) }}</div>
                <p class="mt-2 text-sm leading-6 text-slate-300">{{ stepDescription(step) }}</p>
              </article>
            </div>
          </section>
          <section v-if="generated.media_items?.length">
            <h3 class="mb-2 text-sm font-black text-white">来自诊断的现场图片</h3>
            <p v-if="generated.media_notice" class="mb-3 rounded-md border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-xs leading-5 text-amber-100">
              {{ generated.media_notice }}
            </p>
            <MediaEvidenceGallery :items="generated.media_items" />
          </section>
          <section>
            <h3 class="mb-2 text-sm font-black text-white">安全要求</h3>
            <ul class="space-y-2 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm leading-6 text-slate-300">
              <li v-for="(item, index) in generated.safety_requirements" :key="index">• {{ structuredText(item) }}</li>
            </ul>
          </section>
          <section class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <h3 class="mb-3 text-sm font-black text-white">图谱增强建议</h3>
            <div v-if="hasKgContext" class="grid gap-3 md:grid-cols-2">
              <KgNodeList title="补充工具" :items="generated.kg_tools || []" />
              <KgNodeList title="补充备件" :items="generated.kg_parts || []" />
              <KgNodeList title="安全风险" :items="generated.kg_safety_risks || []" />
              <KgNodeList title="补充步骤" :items="generated.kg_steps || []" />
            </div>
            <EmptyState v-else text="未命中图谱增强，已使用 SOP 模板或规则生成。" />
            <div v-if="generated.kg_evidence?.length" class="mt-3 space-y-2">
              <article v-for="item in generated.kg_evidence.slice(0, 4)" :key="item.id" class="rounded-md bg-black/20 px-3 py-2 text-xs leading-5 text-slate-300">
                {{ item.evidence_text || item.source_type }}
              </article>
            </div>
          </section>
          <section>
            <h3 class="mb-2 text-sm font-black text-white">参考来源</h3>
            <div v-if="generated.references?.length" class="space-y-2">
              <article v-for="(reference, index) in generated.references" :key="index" class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
                <div class="font-bold text-white">{{ reference.document_title || reference.source || '知识来源' }}</div>
                <div class="mt-1 text-xs text-slate-400">
                  切片 {{ reference.chunk_index ?? '-' }} / 相关度 {{ reference.score == null ? '-' : reference.score.toFixed(2) }}
                </div>
              </article>
            </div>
            <EmptyState v-else text="暂无可追溯来源" />
          </section>
        </div>
        <EmptyState v-else text="提交条件后显示后端生成的规程建议。" />
      </DataPanel>
    </div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel :title="editingTemplateId ? '编辑规程模板' : '新增规程模板'">
        <form class="grid gap-3" @submit.prevent="saveTemplate">
          <input v-model.trim="templateForm.title" class="scada-input" required placeholder="模板标题，例如：SUN2000 绝缘阻抗低排查规程" />
          <div class="grid grid-cols-2 gap-3">
            <select v-model="templateForm.manufacturer" class="scada-input">
              <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
            <select v-model="templateForm.product_series" class="scada-input">
              <option v-for="item in templateSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </div>
          <select v-model="templateForm.fault_type" class="scada-input">
            <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="templateForm.maintenance_level" class="scada-input">
            <option value="level_1">一级检修（level_1）</option>
            <option value="level_2">二级检修（level_2）</option>
            <option value="level_3">三级检修（level_3）</option>
          </select>
          <textarea v-model.trim="templateForm.step_instruction" class="scada-input min-h-24" required placeholder="核心作业步骤说明"></textarea>
          <textarea v-model.trim="templateForm.safety_note" class="scada-input min-h-20" placeholder="安全要求"></textarea>
          <div class="flex flex-wrap gap-2">
            <button class="scada-button primary" type="submit" :disabled="savingTemplate">
              <Save :size="16" />
              {{ savingTemplate ? '保存中' : editingTemplateId ? '保存模板' : '创建模板' }}
            </button>
            <button v-if="editingTemplateId" class="scada-button" type="button" @click="resetTemplateForm">取消编辑</button>
          </div>
        </form>
      </DataPanel>

      <DataPanel title="规程模板">
        <div v-if="templates.length" class="space-y-3">
          <article v-for="template in templates" :key="template.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 class="font-black text-white">{{ template.title }}</h3>
                <p class="mt-1 text-xs text-slate-400">{{ labelOf(template.manufacturer) }} / {{ template.product_series || '-' }} / {{ labelOf(template.fault_type) }}</p>
              </div>
              <div class="flex flex-wrap gap-2">
                <StatusPill :value="template.status" />
                <button class="scada-button !min-h-8 !px-3" type="button" @click="editTemplate(template)">编辑</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click="archiveTemplate(template.id)">归档</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click="createExecution(template.id)">开始执行</button>
              </div>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无规程模板" />
      </DataPanel>
    </div>

    <DataPanel title="执行记录">
      <div v-if="executions.length" class="space-y-3">
        <article v-for="execution in executions" :key="String(execution.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 class="font-black text-white">执行记录 {{ execution.id }}</h3>
              <p class="mt-1 text-xs text-slate-400">模板编号（template_id）：{{ execution.template_id }} / {{ formatTime(execution.created_at as string) }}</p>
              <p class="mt-2 text-sm text-slate-300">{{ execution.abnormal_notes || '暂无异常说明' }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <StatusPill :value="String(execution.status || 'not_started')" />
              <button v-if="execution.status === 'not_started'" class="scada-button !min-h-8 !px-3" type="button" @click="updateExecutionStatus(String(execution.id), 'in_progress')">开始</button>
              <button v-if="execution.status === 'in_progress'" class="scada-button !min-h-8 !px-3" type="button" @click="openExecutionResult(execution)">填写结果</button>
              <button v-if="['not_started', 'in_progress'].includes(String(execution.status))" class="scada-button !min-h-8 !px-3" type="button" @click="updateExecutionStatus(String(execution.id), 'aborted')">中止</button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无 SOP 执行记录" />
    </DataPanel>

    <DataPanel v-if="activeExecutionId" title="SOP 执行结果" subtitle="真实记录执行备注、异常情况与复核结论。">
      <form class="grid gap-3 md:grid-cols-2" @submit.prevent="saveExecutionResult">
        <label class="grid gap-1 text-sm font-bold text-slate-200 md:col-span-2">
          执行备注
          <textarea v-model.trim="executionForm.execution_notes" class="scada-input min-h-24" required placeholder="记录各步骤实际执行情况"></textarea>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          异常情况
          <textarea v-model.trim="executionForm.abnormal_notes" class="scada-input min-h-20" placeholder="无异常可填写“未发现异常”"></textarea>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          复核结果
          <textarea v-model.trim="executionForm.review_result" class="scada-input min-h-20" required placeholder="填写安全复核与恢复运行确认"></textarea>
        </label>
        <div class="flex flex-wrap gap-2 md:col-span-2">
          <button class="scada-button primary" type="submit">保存并完成</button>
          <button class="scada-button" type="button" @click="activeExecutionId = ''">取消</button>
        </div>
      </form>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref, watch, type PropType } from 'vue'
import { ClipboardCheck, RefreshCcw, Save } from '@lucide/vue'
import {
  archiveSopTemplateApi,
  createSopExecutionApi,
  createSopTemplateApi,
  generateSopApi,
  getDiagnosisRecordsApi,
  getSopExecutionsApi,
  getSopTemplatesApi,
  updateSopExecutionApi,
  updateSopTemplateApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { formatProviderName } from '@/utils/display'
import { faultTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { SOPGenerateResult, SOPTemplate } from '@/types'

const KgNodeList = defineComponent({
  props: {
    title: { type: String, required: true },
    items: { type: Array as PropType<Array<{ id: string; display_name?: string; canonical_name?: string }>>, required: true }
  },
  setup(props) {
    return () =>
      h('section', [
        h('h4', { class: 'mb-2 text-xs font-black text-cyan-100' }, props.title),
        props.items.length
          ? h(
              'ul',
              { class: 'space-y-1 text-xs text-slate-300' },
              props.items.map((item) =>
                h('li', { class: 'rounded bg-black/20 px-2 py-1', key: item.id }, item.display_name || item.canonical_name || item.id)
              )
            )
          : h('div', { class: 'rounded bg-black/20 px-2 py-1 text-xs text-slate-500' }, '暂无')
      ])
  }
})

const templates = ref<SOPTemplate[]>([])
const executions = ref<Record<string, unknown>[]>([])
const diagnosisRecords = ref<Record<string, unknown>[]>([])
const generated = ref<SOPGenerateResult | null>(null)
const loading = ref(false)
const generating = ref(false)
const savingTemplate = ref(false)
const error = ref('')
const editingTemplateId = ref('')
const activeExecutionId = ref('')
const generateForm = reactive({
  diagnosis_trace_id: '',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  fault_type: 'unknown',
  alarm_code: '',
  enable_kg_enhancement: true
})
const executionForm = reactive({
  execution_notes: '',
  abnormal_notes: '',
  review_result: ''
})
const templateForm = reactive({
  title: '',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  fault_type: 'unknown',
  maintenance_level: 'level_1',
  step_instruction: '',
  safety_note: ''
})

const seriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === generateForm.manufacturer))
const templateSeriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === templateForm.manufacturer))
const hasKgContext = computed(() => Boolean((generated.value?.kg_context?.summary?.matched_node_count as number | undefined) || generated.value?.kg_evidence?.length))

watch(
  () => generateForm.manufacturer,
  () => {
    if (!seriesOptions.value.some((item) => item.value === generateForm.product_series)) {
      generateForm.product_series = seriesOptions.value[0]?.value ?? ''
    }
  }
)

watch(
  () => templateForm.manufacturer,
  () => {
    if (!templateSeriesOptions.value.some((item) => item.value === templateForm.product_series)) {
      templateForm.product_series = templateSeriesOptions.value[0]?.value ?? ''
    }
  }
)

watch(
  () => generateForm.diagnosis_trace_id,
  (traceId) => {
    const record = diagnosisRecords.value.find((item) => String(item.trace_id) === traceId)
    if (!record) return
    generateForm.manufacturer = String(record.manufacturer || generateForm.manufacturer)
    generateForm.product_series = String(record.product_series || generateForm.product_series)
    generateForm.fault_type = String(record.fault_type || generateForm.fault_type)
    generateForm.alarm_code = String(record.alarm_code || '')
  }
)

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [templatePage, executionPage, diagnosisPage] = await Promise.all([
      getSopTemplatesApi({ page: 1, page_size: 50, device_type: 'pv_inverter' }),
      getSopExecutionsApi({ page: 1, page_size: 30 }),
      getDiagnosisRecordsApi({ page: 1, page_size: 50 })
    ])
    templates.value = templatePage.items
    executions.value = executionPage.items
    diagnosisRecords.value = diagnosisPage.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'SOP 数据读取失败'
  } finally {
    loading.value = false
  }
}

async function generate() {
  generating.value = true
  error.value = ''
  generated.value = null
  try {
    const payload: Record<string, unknown> = {
      manufacturer: generateForm.manufacturer,
      product_series: generateForm.product_series,
      device_type: 'pv_inverter',
      fault_type: generateForm.fault_type,
      alarm_code: generateForm.alarm_code || undefined,
      enable_kg_enhancement: generateForm.enable_kg_enhancement
    }
    if (generateForm.diagnosis_trace_id) payload.diagnosis_trace_id = generateForm.diagnosis_trace_id
    generated.value = await generateSopApi(payload)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '规程生成失败'
  } finally {
    generating.value = false
  }
}

async function saveTemplate() {
  savingTemplate.value = true
  error.value = ''
  const payload = {
    title: templateForm.title,
    manufacturer: templateForm.manufacturer,
    product_series: templateForm.product_series,
    device_type: 'pv_inverter',
    fault_type: templateForm.fault_type,
    maintenance_level: templateForm.maintenance_level,
    steps: [
      {
        step_index: 1,
        step_title: '现场排查',
        instruction: templateForm.step_instruction,
        safety_note: templateForm.safety_note || undefined
      }
    ],
    safety_requirements: templateForm.safety_note ? [{ note: templateForm.safety_note }] : [],
    tools_required: [],
    materials_required: [],
    status: 'active',
    version: 1
  }
  try {
    if (editingTemplateId.value) {
      await updateSopTemplateApi(editingTemplateId.value, payload)
      toast('规程模板已更新')
    } else {
      await createSopTemplateApi(payload)
      toast('规程模板已创建')
    }
    resetTemplateForm()
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '规程模板保存失败'
  } finally {
    savingTemplate.value = false
  }
}

function editTemplate(template: SOPTemplate) {
  editingTemplateId.value = template.id
  templateForm.title = template.title
  templateForm.manufacturer = template.manufacturer || 'huawei'
  templateForm.product_series = template.product_series || templateSeriesOptions.value[0]?.value || 'SUN2000'
  templateForm.fault_type = template.fault_type || 'unknown'
  templateForm.maintenance_level = template.maintenance_level || 'level_1'
  const firstStep = template.steps?.[0] as Record<string, unknown> | undefined
  const firstSafety = template.safety_requirements?.[0] as Record<string, unknown> | undefined
  templateForm.step_instruction = String(firstStep?.instruction || '')
  templateForm.safety_note = String(firstStep?.safety_note || firstSafety?.note || '')
}

async function archiveTemplate(id: string) {
  if (!window.confirm('确认归档该 SOP 模板？')) return
  error.value = ''
  try {
    await archiveSopTemplateApi(id)
    toast('规程模板已归档')
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '规程模板归档失败'
  }
}

async function createExecution(templateId: string) {
  error.value = ''
  try {
    await createSopExecutionApi({
      template_id: templateId,
      status: 'not_started',
      step_results: []
    })
    toast('SOP 执行记录已创建')
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'SOP 执行记录创建失败'
  }
}

async function updateExecutionStatus(id: string, status: string) {
  error.value = ''
  try {
    await updateSopExecutionApi(id, {
      status
    })
    toast('SOP 执行状态已更新')
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'SOP 执行状态更新失败'
  }
}

function openExecutionResult(execution: Record<string, unknown>) {
  activeExecutionId.value = String(execution.id)
  executionForm.execution_notes = ''
  executionForm.abnormal_notes = String(execution.abnormal_notes || '')
  const metadata = (execution.metadata_json || {}) as Record<string, unknown>
  executionForm.review_result = String(metadata.review_result || '')
}

async function saveExecutionResult() {
  if (!activeExecutionId.value) return
  error.value = ''
  try {
    const execution = executions.value.find((item) => String(item.id) === activeExecutionId.value)
    const existingSteps = Array.isArray(execution?.step_results)
      ? (execution?.step_results as Record<string, unknown>[])
      : []
    const now = new Date().toISOString()
    const stepResults = existingSteps.map((step, index) => ({
      ...step,
      step_index: Number(step.step_index || index + 1),
      step_title: String(step.step_title || `步骤 ${index + 1}`),
      checked: true,
      note: executionForm.execution_notes,
      checked_at: now
    }))
    if (!stepResults.length) {
      stepResults.push({
        step_index: 1,
        step_title: '执行记录',
        checked: true,
        note: executionForm.execution_notes,
        checked_at: now
      })
    }
    await updateSopExecutionApi(activeExecutionId.value, {
      status: 'completed',
      step_results: stepResults,
      abnormal_notes: executionForm.abnormal_notes || null,
      metadata_json: {
        execution_notes: executionForm.execution_notes,
        review_result: executionForm.review_result
      }
    })
    toast('SOP 执行结果已保存')
    activeExecutionId.value = ''
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'SOP 执行结果保存失败'
  }
}

function resetTemplateForm() {
  editingTemplateId.value = ''
  templateForm.title = ''
  templateForm.manufacturer = 'huawei'
  templateForm.product_series = 'SUN2000'
  templateForm.fault_type = 'unknown'
  templateForm.maintenance_level = 'level_1'
  templateForm.step_instruction = ''
  templateForm.safety_note = ''
}

function labelOf(value?: string | null) {
  const options = [...manufacturerOptions, ...faultTypeOptions]
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

function stepTitle(step: Record<string, unknown>, index: number) {
  return String(step.step_title || step.title || `步骤 ${index + 1}`)
}

function stepDescription(step: Record<string, unknown>) {
  return String(step.instruction || step.description || step.content || structuredText(step))
}

function structuredText(value: unknown) {
  if (!value) return '-'
  if (typeof value === 'string') return value
  if (typeof value !== 'object') return String(value)
  const record = value as Record<string, unknown>
  return String(record.note || record.item || record.description || record.content || JSON.stringify(value))
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(loadAll)
</script>
