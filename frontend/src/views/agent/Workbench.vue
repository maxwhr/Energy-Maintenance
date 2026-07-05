<template>
  <PageFrame
    title="智能体工作台"
    code="AGENTS / WORKBENCH"
    description="面向光伏逆变器故障诊断、SOP 草稿和工单草稿的智能体编排入口；所有高风险动作只生成草稿和审批。"
  >
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="refreshBaseData">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[440px_minmax(0,1fr)]">
      <div class="space-y-4">
        <DataPanel title="运行配置" subtitle="选择智能体、设备、媒体证据和故障上下文。">
          <div class="grid gap-3">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              智能体
              <select v-model="form.agent_code" class="scada-input" data-testid="agent-selector" @change="applyAgentDefaults">
                <option value="multimodal_evidence_agent">多模态证据智能体</option>
                <option value="fault_diagnosis_agent">故障诊断智能体</option>
                <option value="sop_planner_agent">SOP 编排智能体</option>
                <option value="task_orchestration_agent">工单编排智能体</option>
                <option value="knowledge_curator_agent">知识沉淀智能体</option>
              </select>
            </label>

            <label class="grid gap-1 text-sm font-bold text-slate-200">
              设备
              <select v-model="form.device_id" class="scada-input" data-testid="device-selector">
                <option value="">不指定设备</option>
                <option v-for="item in devices" :key="item.id" :value="item.id">
                  {{ item.device_name }} / {{ item.device_code || item.model || '-' }}
                </option>
              </select>
            </label>

            <label class="grid gap-1 text-sm font-bold text-slate-200">
              媒体证据
              <select v-model="form.media_id" class="scada-input" data-testid="media-selector">
                <option value="">不选择媒体</option>
                <option v-for="item in mediaItems" :key="item.id" :value="item.id">
                  {{ item.original_file_name || item.file_name }} / {{ item.alarm_code || '-' }}
                </option>
              </select>
            </label>

            <div class="grid gap-3 md:grid-cols-2">
              <label class="grid gap-1 text-sm font-bold text-slate-200">
                厂家
                <select v-model="form.manufacturer" class="scada-input">
                  <option value="huawei">华为</option>
                  <option value="sungrow">阳光电源</option>
                </select>
              </label>
              <label class="grid gap-1 text-sm font-bold text-slate-200">
                产品系列
                <select v-model="form.product_series" class="scada-input">
                  <option v-for="item in productSeriesForManufacturer" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </label>
            </div>

            <div class="grid gap-3 md:grid-cols-2">
              <label class="grid gap-1 text-sm font-bold text-slate-200">
                故障类型
                <select v-model="form.fault_type" class="scada-input">
                  <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
                </select>
              </label>
              <label class="grid gap-1 text-sm font-bold text-slate-200">
                告警码
                <input v-model.trim="form.alarm_code" class="scada-input" placeholder="例如：低绝缘阻抗告警" />
              </label>
            </div>

            <label class="grid gap-1 text-sm font-bold text-slate-200">
              故障现象 / 编排目标
              <textarea
                v-model.trim="form.input_text"
                class="scada-input min-h-28"
                data-testid="agent-input"
                placeholder="例如：SUN2000 逆变器低绝缘阻抗告警，现场潮湿，设备近期多次重启。"
              ></textarea>
            </label>

            <label v-if="form.agent_code === 'knowledge_curator_agent'" class="grid gap-1 text-sm font-bold text-slate-200">
              工程师备注
              <textarea
                v-model.trim="form.engineer_notes"
                class="scada-input min-h-20"
                data-testid="engineer-notes-input"
                placeholder="例如：现场复测后绝缘恢复，怀疑汇流箱附近湿度导致瞬时告警。"
              ></textarea>
            </label>

            <div v-if="form.agent_code === 'knowledge_curator_agent'" class="grid gap-3 md:grid-cols-2">
              <label class="grid gap-1 text-sm font-bold text-slate-200">
                来源 Run IDs
                <textarea
                  v-model.trim="form.source_agent_run_ids"
                  class="scada-input min-h-20"
                  data-testid="source-runs-input"
                  placeholder="可粘贴诊断 / SOP / 工单智能体 run_id，逗号或换行分隔"
                ></textarea>
              </label>
              <label class="grid gap-1 text-sm font-bold text-slate-200">
                来源 Artifact IDs
                <textarea
                  v-model.trim="form.source_artifact_ids"
                  class="scada-input min-h-20"
                  data-testid="source-artifacts-input"
                  placeholder="可粘贴相关 artifact_id，逗号或换行分隔"
                ></textarea>
              </label>
            </div>

            <div class="grid gap-3 md:grid-cols-2">
              <label class="flex items-center gap-2 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm font-bold text-slate-200">
                <input v-model="form.dry_run" type="checkbox" />
                <span>dry-run：不执行正式写入</span>
              </label>
              <label class="flex items-center gap-2 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm font-bold text-slate-200" :class="!canMock ? 'opacity-60' : ''">
                <input v-model="form.mock_run" type="checkbox" :disabled="!canMock" data-testid="mock-run-checkbox" />
                <span>mock-run：仅专家/管理员可用</span>
              </label>
            </div>

            <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
              <div class="text-xs font-bold text-slate-400">工具链</div>
              <div class="mt-2 flex flex-wrap gap-2">
                <span v-for="tool in activeTools" :key="tool" class="rounded border border-cyan-300/20 bg-cyan-400/10 px-2 py-1 text-xs text-cyan-100">{{ tool }}</span>
              </div>
            </div>

            <button
              class="scada-button primary"
              type="button"
              data-testid="create-agent-run"
              :disabled="isViewer || busy || !form.input_text"
              @click="createRun"
            >
              创建智能体运行
            </button>
            <p v-if="isViewer" class="text-xs text-amber-100">只读用户不能创建 Agent Run 或审批草稿。</p>
          </div>
        </DataPanel>

        <AgentApprovalNotice :approval-status="agentRun?.approval_status" :artifact-count="agentArtifacts.length" />
      </div>

      <div class="space-y-4">
        <DataPanel v-if="agentRun" title="运行结果" subtitle="后端 timeline 聚合返回 run、steps、tool calls、artifacts、approvals 和 events。">
          <div class="grid gap-3 md:grid-cols-3">
            <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
              <div class="text-xs font-bold text-slate-400">run_id</div>
              <div class="mt-1 break-all font-mono text-xs text-cyan-100">{{ agentRun.run_id }}</div>
            </div>
            <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
              <div class="text-xs font-bold text-slate-400">状态</div>
              <div class="mt-1 font-black text-white">{{ agentRun.status }}</div>
            </div>
            <div class="rounded-md border border-slate-600/20 bg-black/20 p-3">
              <div class="text-xs font-bold text-slate-400">置信度</div>
              <div class="mt-1 font-black text-white">{{ agentRun.confidence ?? '-' }}</div>
            </div>
          </div>
          <pre class="mt-3 whitespace-pre-wrap rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-200">{{ agentRun.final_answer }}</pre>
        </DataPanel>

        <AgentDiagnosisSummary :summary="artifactJson('diagnosis_summary')" />
        <AgentSopDraft :draft="artifactJson('sop_draft')" />
        <AgentTaskDraft :draft="artifactJson('task_draft')" />
        <AgentMaintenanceCaseSummary :summary="artifactJson('maintenance_case_summary')" />
        <AgentKnowledgeContributionDraft :draft="artifactJson('knowledge_contribution_draft')" />
        <AgentKgCandidateSuggestion :suggestion="artifactJson('kg_candidate_suggestion')" />
        <AgentConversionResult
          :artifacts="agentArtifacts"
          :approvals="agentApprovals"
          :statuses="conversionStatuses"
          :results="conversionResults"
          :can-convert="canConvertArtifact"
          :is-admin="isAdmin"
          :busy="conversionBusy"
          @convert="convertArtifact"
        />
        <AgentEvidenceTraceSummary :trace="artifactJson('evidence_trace_summary')" />
        <AgentSafetyChecklist :checklist="artifactJson('safety_checklist')" />
        <AgentRunTimeline :steps="agentSteps" />
        <AgentToolCallTable :calls="agentToolCalls" />
        <AgentArtifactPanel :artifacts="agentArtifacts" />
        <AgentApprovalPanel
          :approvals="agentApprovals"
          :can-review="canReview"
          @approve="reviewApproval($event, 'approve')"
          @reject="reviewApproval($event, 'reject')"
        />
      </div>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RefreshCcw } from '@lucide/vue'
import {
  approveAgentApproval,
  convertAgentArtifact,
  createAgentRun,
  getAgentArtifactConversionStatus,
  getAgentRunTimeline,
  getDevicesApi,
  getMediaApi,
  rejectAgentApproval
} from '@/api'
import AgentApprovalNotice from '@/components/AgentApprovalNotice.vue'
import AgentApprovalPanel from '@/components/AgentApprovalPanel.vue'
import AgentArtifactPanel from '@/components/AgentArtifactPanel.vue'
import AgentConversionResult from '@/components/AgentConversionResult.vue'
import AgentDiagnosisSummary from '@/components/AgentDiagnosisSummary.vue'
import AgentEvidenceTraceSummary from '@/components/AgentEvidenceTraceSummary.vue'
import AgentKgCandidateSuggestion from '@/components/AgentKgCandidateSuggestion.vue'
import AgentKnowledgeContributionDraft from '@/components/AgentKnowledgeContributionDraft.vue'
import AgentMaintenanceCaseSummary from '@/components/AgentMaintenanceCaseSummary.vue'
import AgentRunTimeline from '@/components/AgentRunTimeline.vue'
import AgentSafetyChecklist from '@/components/AgentSafetyChecklist.vue'
import AgentSopDraft from '@/components/AgentSopDraft.vue'
import AgentTaskDraft from '@/components/AgentTaskDraft.vue'
import AgentToolCallTable from '@/components/AgentToolCallTable.vue'
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { useUserStore } from '@/stores/user'
import { faultTypeOptions, productSeriesOptions, type DeviceItem, type UploadedMediaItem } from '@/types'
import type {
  AgentApproval,
  AgentArtifact,
  AgentArtifactConversionResult,
  AgentArtifactConversionStatus,
  AgentConversionTargetType,
  AgentRun,
  AgentStep,
  AgentToolCall
} from '@/types/agent'

const userStore = useUserStore()
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const devices = ref<DeviceItem[]>([])
const mediaItems = ref<UploadedMediaItem[]>([])
const agentRun = ref<AgentRun | null>(null)
const agentSteps = ref<AgentStep[]>([])
const agentToolCalls = ref<AgentToolCall[]>([])
const agentArtifacts = ref<AgentArtifact[]>([])
const agentApprovals = ref<AgentApproval[]>([])
const conversionStatuses = ref<Record<string, AgentArtifactConversionStatus | undefined>>({})
const conversionResults = ref<AgentArtifactConversionResult[]>([])
const conversionBusy = ref(false)

const defaults: Record<string, { text: string; tools: string[]; mediaRequired?: boolean }> = {
  multimodal_evidence_agent: {
    text: '结合所选媒体证据，执行光伏逆变器多模态证据 dry-run 分析，并说明 blocked/mock 边界。',
    tools: ['media_lookup', 'media_ocr', 'media_mimo_analysis', 'safety_guard'],
    mediaRequired: true
  },
  fault_diagnosis_agent: {
    text: 'SUN2000 逆变器低绝缘阻抗告警，现场潮湿，设备近期多次重启，请生成诊断摘要、证据追溯和安全复核清单。',
    tools: ['device_lookup', 'device_history', 'media_lookup', 'knowledge_search', 'kg_business_context', 'diagnosis_rule_engine', 'safety_guard']
  },
  sop_planner_agent: {
    text: '基于低绝缘阻抗告警和现场潮湿现象，生成光伏逆变器检修 SOP 草稿，并列出审批前复核要点。',
    tools: ['device_lookup', 'knowledge_search', 'kg_business_context', 'sop_generator', 'safety_guard']
  },
  task_orchestration_agent: {
    text: '为低绝缘阻抗告警生成检修工单草稿，包含优先级、安全要求、履历依据和人工审批说明。',
    tools: ['device_lookup', 'device_history', 'record_center_lookup', 'task_draft_creator', 'safety_guard', 'human_approval']
  },
  knowledge_curator_agent: {
    text: '请将本次 SUN2000 低绝缘阻抗告警的诊断、SOP 草稿、工单草稿、媒体证据和工程师备注沉淀为一线经验案例草稿。',
    tools: [
      'device_lookup',
      'device_history',
      'record_center_lookup',
      'knowledge_search',
      'kg_business_context',
      'media_lookup',
      'safety_guard',
      'knowledge_contribution_draft_creator',
      'human_approval'
    ]
  }
}

const form = reactive({
  agent_code: 'fault_diagnosis_agent',
  device_id: '',
  media_id: '',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  fault_type: 'low_insulation_resistance',
  alarm_code: '低绝缘阻抗告警',
  input_text: defaults.fault_diagnosis_agent.text,
  engineer_notes: '',
  source_agent_run_ids: '',
  source_artifact_ids: '',
  dry_run: true,
  mock_run: false
})

const isViewer = computed(() => userStore.role === 'viewer')
const canMock = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const canReview = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const canConvertArtifact = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const isAdmin = computed(() => userStore.role === 'admin')
const activeTools = computed(() => defaults[form.agent_code]?.tools || [])
const productSeriesForManufacturer = computed(() =>
  productSeriesOptions.filter((item) => item.manufacturer === form.manufacturer)
)
const convertibleArtifactTypes = new Set([
  'knowledge_contribution_draft',
  'sop_draft',
  'task_draft',
  'kg_candidate_suggestion'
])

watch(
  () => form.manufacturer,
  () => {
    const first = productSeriesForManufacturer.value[0]
    if (first && !productSeriesForManufacturer.value.some((item) => item.value === form.product_series)) {
      form.product_series = first.value
    }
  }
)

function applyAgentDefaults() {
  const current = defaults[form.agent_code]
  if (!current) return
  form.input_text = current.text
  if (!canMock.value) form.mock_run = false
}

async function refreshBaseData() {
  loading.value = true
  error.value = ''
  try {
    const [devicePage, mediaPage] = await Promise.all([
      getDevicesApi({ page: 1, page_size: 50, device_type: 'pv_inverter' }),
      getMediaApi({ page: 1, page_size: 50, device_type: 'pv_inverter' })
    ])
    devices.value = devicePage.items
    mediaItems.value = mediaPage.items
    if (!form.device_id && devices.value[0]) form.device_id = devices.value[0].id
    if (!form.media_id && mediaItems.value[0]) form.media_id = mediaItems.value[0].id
  } catch (err) {
    setError(err, '智能体基础数据加载失败')
  } finally {
    loading.value = false
  }
}

async function createRun() {
  if (isViewer.value) {
    error.value = '只读用户不能创建 Agent Run。'
    return
  }
  if (form.mock_run && !canMock.value) {
    error.value = '当前账号没有 mock-run 权限。'
    form.mock_run = false
    return
  }
  if (defaults[form.agent_code]?.mediaRequired && !form.media_id) {
    error.value = '多模态证据智能体需要先选择媒体。'
    return
  }
  busy.value = true
  error.value = ''
  try {
    const mediaIds = form.media_id ? [form.media_id] : []
    const run = await createAgentRun({
      agent_code: form.agent_code,
      input_text: form.input_text,
      device_id: form.device_id || null,
      media_ids: mediaIds,
      tools: activeTools.value,
      dry_run: form.dry_run,
      mock_run: form.mock_run,
      context: {
        manufacturer: form.manufacturer,
        product_series: form.product_series,
        device_type: 'pv_inverter',
        fault_type: form.fault_type,
        alarm_code: form.alarm_code,
        fault_description: form.input_text,
        engineer_notes: form.engineer_notes,
        source_agent_run_ids: parseIdList(form.source_agent_run_ids),
        source_artifact_ids: parseIdList(form.source_artifact_ids),
        source: 'agent_workbench'
      },
      tool_inputs: {
        media_ocr: { mock_run: form.mock_run, capability: 'ocr' },
        media_mimo_analysis: { mock_run: form.mock_run, capability: 'fault_scene_analysis', analysis_type: 'fault_scene' },
        task_draft_creator: { priority: 'high' },
        knowledge_contribution_draft_creator: { category: 'maintenance_experience' },
        safety_guard: { source: form.agent_code }
      }
    })
    await loadTimeline(run.run_id)
    toast('智能体运行已完成，结果来自后端 timeline。')
  } catch (err) {
    setError(err, 'Agent Run 创建失败')
  } finally {
    busy.value = false
  }
}

async function loadTimeline(runId: string) {
  const timeline = await getAgentRunTimeline(runId)
  agentRun.value = timeline.run
  agentSteps.value = timeline.steps
  agentToolCalls.value = timeline.tool_calls
  agentArtifacts.value = timeline.artifacts
  agentApprovals.value = timeline.approvals
  await loadConversionStatuses(timeline.artifacts)
}

async function loadConversionStatuses(artifacts: AgentArtifact[]) {
  const convertibleArtifacts = artifacts.filter((item) => convertibleArtifactTypes.has(item.artifact_type))
  if (!convertibleArtifacts.length) {
    conversionStatuses.value = {}
    return
  }
  const entries = await Promise.all(
    convertibleArtifacts.map(async (artifact) => {
      try {
        const status = await getAgentArtifactConversionStatus(artifact.id)
        return [artifact.id, status] as const
      } catch {
        return [artifact.id, undefined] as const
      }
    })
  )
  conversionStatuses.value = Object.fromEntries(entries)
}

async function convertArtifact(
  artifactId: string,
  targetType: AgentConversionTargetType,
  approvalId: string,
  overrideWarnings: boolean
) {
  if (!canConvertArtifact.value) {
    error.value = '\u5f53\u524d\u8d26\u53f7\u6ca1\u6709\u8349\u7a3f\u8f6c\u6362\u6743\u9650\u3002'
    return
  }
  conversionBusy.value = true
  error.value = ''
  try {
    const result = await convertAgentArtifact(artifactId, {
      target_type: targetType,
      approval_id: approvalId || null,
      override_warnings: overrideWarnings,
      comment: 'agent_workbench_manual_conversion'
    })
    conversionResults.value = [result, ...conversionResults.value].slice(0, 8)
    if (agentRun.value) {
      await loadTimeline(agentRun.value.run_id)
    } else {
      await loadConversionStatuses(agentArtifacts.value)
    }
    toast('\u8349\u7a3f\u5df2\u8f6c\u4e3a\u6b63\u5f0f\u4e1a\u52a1\u5bf9\u8c61')
  } catch (err) {
    setError(err, '\u8349\u7a3f\u8f6c\u6362\u5931\u8d25')
  } finally {
    conversionBusy.value = false
  }
}

async function reviewApproval(approvalId: string, action: 'approve' | 'reject') {
  if (!canReview.value) {
    error.value = '当前账号没有审批权限。'
    return
  }
  try {
    if (action === 'approve') {
      await approveAgentApproval(approvalId, '智能体工作台前端审批验证：草稿通过。')
    } else {
      await rejectAgentApproval(approvalId, '智能体工作台前端审批验证：草稿驳回。')
    }
    if (agentRun.value) await loadTimeline(agentRun.value.run_id)
    toast(action === 'approve' ? '草稿审批已通过' : '草稿审批已驳回')
  } catch (err) {
    setError(err, '审批操作失败')
  }
}

function artifactJson(type: string) {
  return agentArtifacts.value.find((item) => item.artifact_type === type)?.content_json || null
}

function parseIdList(value: string) {
  return value
    .split(/[\n,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function setError(err: unknown, fallback: string) {
  error.value = err instanceof Error ? err.message : fallback
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(refreshBaseData)
</script>
