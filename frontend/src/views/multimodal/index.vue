<template>
  <PageFrame
    title="多模态证据中心"
    code="MULTIMODAL / EVIDENCE"
    description="统一管理图片 OCR、AI 多模态分析、证据链接和人工复核；当前真实外部 API 未配置时不会外呼。"
  >
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="refreshAll">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <div class="space-y-4">
        <DataPanel title="媒体选择" subtitle="选择一个现场图片后查看 OCR、AI 分析和证据链。">
          <div class="grid gap-3">
            <input v-model.trim="mediaFilters.keyword" class="scada-input" placeholder="搜索文件名、说明或告警代码" @keyup.enter="loadMedia" />
            <div class="grid grid-cols-2 gap-3">
              <select v-model="mediaFilters.manufacturer" class="scada-input">
                <option value="">全部厂家</option>
                <option value="huawei">华为</option>
                <option value="sungrow">阳光电源</option>
              </select>
              <select v-model="mediaFilters.fault_type" class="scada-input">
                <option value="">全部故障</option>
                <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </div>
            <button class="scada-button" type="button" :disabled="loading" @click="loadMedia">
              <Search :size="16" />
              查询媒体
            </button>
          </div>

          <div class="mt-4 space-y-2">
            <button
              v-for="item in mediaItems"
              :key="item.id"
              class="w-full rounded-md border p-3 text-left transition"
              :class="selectedMediaId === item.id ? 'border-cyan-300/60 bg-cyan-400/10' : 'border-slate-600/20 bg-black/20 hover:border-cyan-300/30'"
              type="button"
              @click="selectMedia(item.id)"
            >
              <div class="font-black text-white">{{ item.original_file_name || item.file_name }}</div>
              <div class="mt-1 text-xs text-slate-400">{{ item.manufacturer || '-' }} / {{ item.product_series || '-' }} / {{ item.alarm_code || '-' }}</div>
              <div class="mt-1 text-xs text-slate-500">{{ formatTime(item.created_at) }}</div>
            </button>
            <EmptyState v-if="!mediaItems.length" text="暂无媒体资料，请先在媒体资料页上传现场图片。" />
          </div>
        </DataPanel>

        <MultimodalProviderPanel
          :providers="providers"
          :loading="loading"
          :readonly="isViewer"
          :can-check="isAdmin"
          :can-mock="canMock"
          :can-real="canReal"
          :last-result="lastProviderResult"
          @refresh="loadProviderStatus"
          @check="checkProvider"
          @dry-run="dryRunProvider"
          @mock-run="mockRunProvider"
          @real-run="realRunProvider"
        />
      </div>

      <div class="space-y-4">
        <MultimodalEvidenceSummary :summary="summary" />

        <MultimodalJobPanel
          :media-id="selectedMediaId"
          :jobs="jobs"
          :busy="jobBusy"
          :readonly="isViewer"
          :can-mock="canMock"
          @create-ocr-dry-run="createJob('ocr', false)"
          @create-ai-dry-run="createJob('multimodal_analysis', false)"
          @create-ai-mock-run="createJob('multimodal_analysis', true)"
          @create-ocr-mock-run="createJob('ocr', true)"
        />

        <MultimodalOcrPanel :results="ocrResults" />
        <MultimodalAnalysisPanel :analyses="analyses" :can-review="canReview" @review="reviewAiAnalysis" />

        <DataPanel title="证据链接" subtitle="将媒体证据关联到任务、诊断、问答、记录中心或 Agent Run。">
          <form v-if="!isViewer" class="mb-4 grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]" @submit.prevent="createEvidence">
            <select v-model="evidenceForm.source_type" class="scada-input">
              <option value="agent_run">Agent Run</option>
              <option value="diagnosis">诊断记录</option>
              <option value="retrieval">检修问答</option>
              <option value="maintenance_task">检修任务</option>
              <option value="record_center">记录中心</option>
            </select>
            <input v-model.trim="evidenceForm.source_id" class="scada-input" placeholder="来源 ID / trace_id" />
            <select v-model="evidenceForm.relation_type" class="scada-input">
              <option value="supports">支持</option>
              <option value="used_as_context">作为上下文</option>
              <option value="attached_to">附件关联</option>
              <option value="generated_from">生成自</option>
            </select>
            <button class="scada-button primary" type="submit" :disabled="!selectedMediaId || evidenceBusy">创建链接</button>
          </form>
          <div v-if="evidenceLinks.length" class="space-y-2">
            <article v-for="item in evidenceLinks" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm text-slate-300">
              <span class="font-bold text-white">{{ item.source_type }}</span>
              <span class="mx-2 text-slate-500">/</span>
              {{ item.source_id }}
              <span class="mx-2 text-slate-500">/</span>
              {{ item.relation_type }}
            </article>
          </div>
          <EmptyState v-else text="暂无证据链接。" />
        </DataPanel>

        <DataPanel title="智能体工作台入口" subtitle="创建 dry-run Agent Run，追踪 steps、tool calls、artifacts、approvals 和 events。">
          <div class="grid gap-3 lg:grid-cols-2">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              智能体
              <select v-model="agentForm.agent_code" class="scada-input">
                <option v-for="agent in agentDefinitions" :key="agent.agent_code" :value="agent.agent_code">
                  {{ agent.agent_name }} / {{ agent.agent_code }}
                </option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              工具组合
              <div class="grid grid-cols-2 gap-2 rounded-md border border-slate-600/20 bg-black/20 p-3">
                <label v-for="tool in visibleAgentTools" :key="tool.tool_name" class="flex items-center gap-2 text-xs">
                  <input v-model="agentForm.tools" type="checkbox" :value="tool.tool_name" />
                  <span>{{ tool.tool_display_name || tool.tool_name }}</span>
                </label>
              </div>
            </label>
          </div>
          <label class="mt-3 grid gap-1 text-sm font-bold text-slate-200">
            任务描述
            <textarea v-model.trim="agentForm.input_text" class="scada-input min-h-24" placeholder="例如：结合所选媒体证据，检查华为 SUN2000 告警画面并生成安全边界说明。"></textarea>
          </label>
          <div class="mt-3 grid gap-3 md:grid-cols-2">
            <label class="flex items-center gap-2 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm font-bold text-slate-200">
              <input v-model="agentForm.dry_run" type="checkbox" />
              <span>dry-run：不调用真实外部 API</span>
            </label>
            <label class="flex items-center gap-2 rounded-md border border-slate-600/20 bg-black/20 p-3 text-sm font-bold text-slate-200" :class="!canMock ? 'opacity-60' : ''">
              <input v-model="agentForm.mock_run" type="checkbox" :disabled="!canMock" />
              <span>mock-run：生成本地模拟 OCR / AI 证据</span>
            </label>
          </div>
          <div class="mt-3 flex flex-wrap gap-2">
            <button class="scada-button primary" type="button" :disabled="!canCreateAgentRun || agentBusy || !selectedMediaId" @click="createAgentDryRun">
              创建多模态证据智能体运行
            </button>
            <span v-if="isViewer" class="text-xs text-amber-100">只读用户不能创建 Agent Run。</span>
            <span v-else-if="!selectedMediaId" class="text-xs text-amber-100">请先选择媒体图片。</span>
            <span v-if="!canMock" class="text-xs text-slate-400">当前角色仅允许 dry-run，不能 mock-run。</span>
          </div>
        </DataPanel>

        <DataPanel v-if="agentRun" title="智能体运行结果" subtitle="后端 timeline 聚合返回 run、steps、tool calls、artifacts、approvals 和 events。">
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

        <AgentEvidenceSummary :summary="agentEvidenceSummary" />
        <AgentSafetyChecklist :checklist="agentSafetyChecklist" />
        <AgentRunTimeline :steps="agentSteps" />
        <AgentToolCallTable :calls="agentToolCalls" />
        <AgentArtifactPanel :artifacts="agentArtifacts" />
        <DataPanel v-if="agentTraceSummary" title="证据追溯摘要" subtitle="仅展示追溯关键编号，完整 JSON 在 artifact 中折叠查看。">
          <div class="grid gap-2 text-sm text-slate-300 md:grid-cols-2">
            <div>媒体数量：{{ traceList('media_ids').length }}</div>
            <div>工具调用：{{ traceList('tool_call_ids').length }}</div>
            <div>证据链：{{ traceList('evidence_link_ids').length }}</div>
            <div>外部 trace：{{ traceList('external_trace_ids').length }}</div>
          </div>
        </DataPanel>
        <AgentApprovalPanel :approvals="agentApprovals" />
      </div>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { RefreshCcw, Search } from '@lucide/vue'
import {
  checkExternalApiProvider,
  checkRealExternalApi,
  createAgentRun,
  createEvidenceLink,
  createMediaProcessingJob,
  dryRunExternalApi,
  getAgentArtifacts,
  getAgentDefinitions,
  getAgentEvents,
  getAgentRunApprovals,
  getAgentRunDetail,
  getAgentRunSteps,
  getAgentRunTimeline,
  getAgentRunToolCalls,
  getAgentTools,
  getEvidenceLinks,
  getExternalApiLogs,
  getExternalApiStatus,
  getMediaAnalyses,
  getMediaApi,
  getMediaJobs,
  getMediaMultimodalSummary,
  getMediaOcrResults,
  mockRunExternalApi,
  reviewAnalysis
} from '@/api'
import AgentApprovalPanel from '@/components/AgentApprovalPanel.vue'
import AgentArtifactPanel from '@/components/AgentArtifactPanel.vue'
import AgentEvidenceSummary from '@/components/AgentEvidenceSummary.vue'
import AgentRunTimeline from '@/components/AgentRunTimeline.vue'
import AgentSafetyChecklist from '@/components/AgentSafetyChecklist.vue'
import AgentToolCallTable from '@/components/AgentToolCallTable.vue'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MultimodalAnalysisPanel from '@/components/MultimodalAnalysisPanel.vue'
import MultimodalEvidenceSummary from '@/components/MultimodalEvidenceSummary.vue'
import MultimodalJobPanel from '@/components/MultimodalJobPanel.vue'
import MultimodalOcrPanel from '@/components/MultimodalOcrPanel.vue'
import MultimodalProviderPanel from '@/components/MultimodalProviderPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { useUserStore } from '@/stores/user'
import { faultTypeOptions } from '@/types'
import type { ExternalApiGatewayResult, ExternalApiProviderStatus, UploadedMediaItem } from '@/types'
import type { AgentApproval, AgentArtifact, AgentDefinition, AgentEventLog, AgentRun, AgentStep, AgentTool, AgentToolCall } from '@/types/agent'
import type { MediaAIAnalysis, MediaEvidenceLink, MediaMultimodalSummary, MediaOCRResult, MediaProcessingJob } from '@/types/multimodal'

const route = useRoute()
const userStore = useUserStore()

const loading = ref(false)
const error = ref('')
const jobBusy = ref(false)
const evidenceBusy = ref(false)
const agentBusy = ref(false)
const mediaItems = ref<UploadedMediaItem[]>([])
const selectedMediaId = ref<string>('')
const summary = ref<MediaMultimodalSummary | null>(null)
const jobs = ref<MediaProcessingJob[]>([])
const ocrResults = ref<MediaOCRResult[]>([])
const analyses = ref<MediaAIAnalysis[]>([])
const evidenceLinks = ref<MediaEvidenceLink[]>([])
const providers = ref<ExternalApiProviderStatus[]>([])
const lastProviderResult = ref<ExternalApiGatewayResult | null>(null)
const agentDefinitions = ref<AgentDefinition[]>([])
const agentTools = ref<AgentTool[]>([])
const agentRun = ref<AgentRun | null>(null)
const agentSteps = ref<AgentStep[]>([])
const agentToolCalls = ref<AgentToolCall[]>([])
const agentArtifacts = ref<AgentArtifact[]>([])
const agentApprovals = ref<AgentApproval[]>([])
const agentEvents = ref<AgentEventLog[]>([])

const mediaFilters = reactive({ keyword: '', manufacturer: '', fault_type: '' })
const evidenceForm = reactive({ source_type: 'agent_run', source_id: '', relation_type: 'supports' })
const agentForm = reactive({
  agent_code: 'multimodal_evidence_agent',
  input_text: '结合所选媒体证据，执行光伏逆变器多模态证据 dry-run 分析，并说明 blocked/mock 边界。',
  tools: ['media_lookup', 'media_ocr', 'media_mimo_analysis', 'safety_guard'],
  dry_run: true,
  mock_run: false
})

const isViewer = computed(() => userStore.role === 'viewer')
const isAdmin = computed(() => userStore.role === 'admin')
const canMock = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const canReal = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const canReview = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const canCreateAgentRun = computed(() => !isViewer.value)
const visibleAgentTools = computed(() => agentTools.value.filter((item) => ['media_lookup', 'media_ocr', 'media_mimo_analysis', 'safety_guard'].includes(item.tool_name)))
const agentEvidenceSummary = computed(() => artifactJson('multimodal_evidence_summary'))
const agentSafetyChecklist = computed(() => artifactJson('safety_checklist'))
const agentTraceSummary = computed(() => artifactJson('evidence_trace_summary'))

async function refreshAll() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadProviderStatus(), loadMedia(), loadAgents()])
    if (selectedMediaId.value) await loadSelectedMediaContext()
  } catch (err) {
    setError(err, '多模态证据中心刷新失败')
  } finally {
    loading.value = false
  }
}

async function loadMedia() {
  const params: Record<string, string | number> = { page: 1, page_size: 30, device_type: 'pv_inverter' }
  if (mediaFilters.keyword) params.keyword = mediaFilters.keyword
  if (mediaFilters.manufacturer) params.manufacturer = mediaFilters.manufacturer
  if (mediaFilters.fault_type) params.fault_type = mediaFilters.fault_type
  const result = await getMediaApi(params)
  mediaItems.value = result.items
  const queryMediaId = typeof route.query.media_id === 'string' ? route.query.media_id : ''
  if (!selectedMediaId.value && queryMediaId) selectedMediaId.value = queryMediaId
  if (!selectedMediaId.value && mediaItems.value[0]) selectedMediaId.value = mediaItems.value[0].id
}

async function selectMedia(mediaId: string) {
  selectedMediaId.value = mediaId
  await loadSelectedMediaContext()
}

async function loadSelectedMediaContext() {
  if (!selectedMediaId.value) return
  const mediaId = selectedMediaId.value
  const [summaryData, jobData, ocrData, analysisData, linkData] = await Promise.all([
    getMediaMultimodalSummary(mediaId),
    getMediaJobs(mediaId, { page: 1, page_size: 20 }),
    getMediaOcrResults(mediaId, { page: 1, page_size: 20 }),
    getMediaAnalyses(mediaId, { page: 1, page_size: 20 }),
    getEvidenceLinks({ media_id: mediaId, page: 1, page_size: 20 })
  ])
  summary.value = summaryData
  jobs.value = jobData.items
  ocrResults.value = ocrData.items
  analyses.value = analysisData.items
  evidenceLinks.value = linkData.items
}

async function loadProviderStatus() {
  const data = await getExternalApiStatus()
  providers.value = data.providers
}

async function loadAgents() {
  const [definitions, tools] = await Promise.all([getAgentDefinitions(), getAgentTools()])
  agentDefinitions.value = definitions
  agentTools.value = tools
  if (!agentDefinitions.value.find((item) => item.agent_code === agentForm.agent_code) && agentDefinitions.value[0]) {
    agentForm.agent_code = agentDefinitions.value[0].agent_code
  }
}

async function createJob(jobType: 'ocr' | 'multimodal_analysis', mockRun: boolean) {
  if (!selectedMediaId.value) {
    error.value = '请先选择媒体。'
    return
  }
  if (isViewer.value) {
    error.value = '只读用户不能创建处理任务。'
    return
  }
  if (mockRun && !canMock.value) {
    error.value = '当前账号没有 mock-run 权限。'
    return
  }
  jobBusy.value = true
  error.value = ''
  try {
    await createMediaProcessingJob(selectedMediaId.value, {
      job_type: jobType,
      provider_code: jobType === 'ocr' ? 'tesseract_ocr' : 'mimo_2_5',
      capability: jobType === 'ocr' ? 'ocr' : 'fault_scene_analysis',
      analysis_type: jobType === 'ocr' ? undefined : 'fault_scene',
      dry_run: !mockRun,
      mock_run: mockRun,
      input_summary: {
        source: 'multimodal_frontend',
        media_id: selectedMediaId.value,
        note: mockRun ? 'frontend mock-run; no real external API call' : 'frontend dry-run; no real external API call'
      }
    })
    toast(mockRun ? 'mock-run 已完成，结果已标记为模拟证据' : 'dry-run 任务已创建')
    await loadSelectedMediaContext()
  } catch (err) {
    setError(err, '处理任务创建失败')
  } finally {
    jobBusy.value = false
  }
}

async function reviewAiAnalysis(id: string, status: 'accepted' | 'rejected' | 'revised') {
  if (!canReview.value) {
    error.value = '当前账号没有人工复核权限。'
    return
  }
  try {
    await reviewAnalysis(id, { human_review_status: status, review_comment: '前端多模态证据中心复核。' })
    toast('复核状态已更新')
    await loadSelectedMediaContext()
  } catch (err) {
    setError(err, 'AI 分析复核失败')
  }
}

async function createEvidence() {
  if (!selectedMediaId.value) {
    error.value = '请先选择媒体。'
    return
  }
  if (!evidenceForm.source_id) {
    error.value = '请输入来源 ID 或 trace_id。'
    return
  }
  evidenceBusy.value = true
  try {
    await createEvidenceLink({
      media_id: selectedMediaId.value,
      analysis_id: analyses.value[0]?.id || null,
      ocr_result_id: ocrResults.value[0]?.id || null,
      source_type: evidenceForm.source_type,
      source_id: evidenceForm.source_id,
      relation_type: evidenceForm.relation_type
    })
    toast('证据链接已创建')
    await loadSelectedMediaContext()
  } catch (err) {
    setError(err, '证据链接创建失败')
  } finally {
    evidenceBusy.value = false
  }
}

async function checkProvider(providerCode: string) {
  try {
    lastProviderResult.value = await checkExternalApiProvider(providerCode)
    await loadProviderStatus()
  } catch (err) {
    setError(err, 'Provider 检查失败')
  }
}

async function dryRunProvider(providerCode: string) {
  try {
    lastProviderResult.value = await dryRunExternalApi({
      provider_code: providerCode,
      capability: capabilityForProvider(providerCode),
      input_summary: { source: 'multimodal_frontend', media_ids: selectedMediaId.value ? [selectedMediaId.value] : [], image_count: selectedMediaId.value ? 1 : 0 }
    })
    await getExternalApiLogs({ page: 1, page_size: 5 })
  } catch (err) {
    setError(err, 'Provider dry-run 失败')
  }
}

async function mockRunProvider(providerCode: string) {
  if (!canMock.value) return
  try {
    lastProviderResult.value = await mockRunExternalApi({
      provider_code: providerCode,
      capability: capabilityForProvider(providerCode),
      input_summary: { source: 'multimodal_frontend', media_ids: selectedMediaId.value ? [selectedMediaId.value] : [], image_count: selectedMediaId.value ? 1 : 0 }
    })
  } catch (err) {
    setError(err, 'Provider mock-run 失败')
  }
}

async function realRunProvider(providerCode: string) {
  if (!canReal.value) return
  try {
    const capability = capabilityForProvider(providerCode)
    if (providerCode === 'mimo_2_5' || providerCode.includes('vision')) {
      if (!selectedMediaId.value) {
        error.value = '请先选择媒体图片，再执行受控 real-run。'
        return
      }
      await createMediaProcessingJob(selectedMediaId.value, {
        job_type: 'multimodal_analysis',
        provider_code: providerCode,
        capability,
        analysis_type: 'fault_scene',
        dry_run: false,
        mock_run: false,
        real_run: true,
        input_summary: {
          source: 'multimodal_frontend_real_run',
          media_id: selectedMediaId.value,
          note: 'frontend controlled real-run; backend loads media content and sanitizes logs'
        }
      })
      toast('real-run 已提交，真实外部结果仅作为辅助证据并需要人工复核。')
      await loadSelectedMediaContext()
      return
    }
    if (providerCode.includes('ocr') && providerCode !== 'tesseract_ocr') {
      if (!selectedMediaId.value) {
        error.value = '请先选择媒体图片，再执行 OCR real-run。'
        return
      }
      await createMediaProcessingJob(selectedMediaId.value, {
        job_type: 'ocr',
        provider_code: providerCode,
        capability: 'ocr',
        dry_run: false,
        mock_run: false,
        real_run: true,
        input_summary: {
          source: 'multimodal_frontend_real_run',
          media_id: selectedMediaId.value,
          note: 'frontend controlled OCR real-run; backend loads media content and sanitizes logs'
        }
      })
      toast('OCR real-run 已提交，识别结果仅作为辅助证据并需要人工复核。')
      await loadSelectedMediaContext()
      return
    }
    lastProviderResult.value = await checkRealExternalApi({
      provider_code: providerCode,
      capability,
      real_run: true,
      input_summary: {
        source: 'multimodal_frontend_real_run',
        prompt: 'Task24C controlled provider real-run check for PV inverter maintenance assistant.',
        media_ids: selectedMediaId.value ? [selectedMediaId.value] : []
      }
    })
    await loadProviderStatus()
  } catch (err) {
    setError(err, 'Provider real-run 失败')
  }
}

async function createAgentDryRun() {
  if (isViewer.value) {
    error.value = '只读用户不能创建 Agent Run。'
    return
  }
  if (!selectedMediaId.value) {
    error.value = '请先选择媒体图片。'
    return
  }
  if (agentForm.mock_run && !canMock.value) {
    error.value = '当前账号没有 mock-run 权限。'
    agentForm.mock_run = false
    return
  }
  agentBusy.value = true
  error.value = ''
  try {
    const run = await createAgentRun({
      agent_code: agentForm.agent_code,
      input_text: agentForm.input_text,
      media_ids: selectedMediaId.value ? [selectedMediaId.value] : [],
      tools: agentForm.tools,
      context: {
        agent_code: agentForm.agent_code,
        manufacturer: 'huawei',
        product_series: 'SUN2000',
        device_type: 'pv_inverter',
        source: 'multimodal_frontend'
      },
      tool_inputs: {
        media_lookup: { selected_from: 'multimodal_frontend' },
        media_mimo_analysis: { mock_run: agentForm.mock_run, capability: 'fault_scene_analysis', analysis_type: 'fault_scene' },
        media_ocr: { mock_run: agentForm.mock_run, capability: 'ocr' },
        safety_guard: { source: 'multimodal_evidence_agent' }
      },
      dry_run: agentForm.dry_run,
      mock_run: agentForm.mock_run
    })
    await loadAgentDetail(run.run_id)
    evidenceForm.source_type = 'agent_run'
    evidenceForm.source_id = run.run_id
    await loadSelectedMediaContext()
    toast(agentForm.mock_run ? '多模态证据智能体 mock-run 已完成' : '多模态证据智能体 dry-run 已完成')
  } catch (err) {
    setError(err, 'Agent Run 创建失败')
  } finally {
    agentBusy.value = false
  }
}

async function loadAgentDetail(runId: string) {
  try {
    const timeline = await getAgentRunTimeline(runId)
    agentRun.value = timeline.run
    agentSteps.value = timeline.steps
    agentToolCalls.value = timeline.tool_calls
    agentArtifacts.value = timeline.artifacts
    agentApprovals.value = timeline.approvals
    agentEvents.value = timeline.events
    return
  } catch {
    const [detail, steps, calls, artifacts, approvals, events] = await Promise.all([
      getAgentRunDetail(runId),
      getAgentRunSteps(runId),
      getAgentRunToolCalls(runId),
      getAgentArtifacts(runId),
      getAgentRunApprovals(runId),
      getAgentEvents({ run_id: runId, page: 1, page_size: 50 })
    ])
    agentRun.value = detail.run
    agentSteps.value = steps.length ? steps : detail.steps
    agentToolCalls.value = calls.length ? calls : detail.tool_calls
    agentArtifacts.value = artifacts.length ? artifacts : detail.artifacts
    agentApprovals.value = approvals.length ? approvals : detail.approvals
    agentEvents.value = events.items
  }
}

function artifactJson(type: string) {
  return agentArtifacts.value.find((item) => item.artifact_type === type)?.content_json || null
}

function traceList(key: string) {
  const value = agentTraceSummary.value?.[key]
  return Array.isArray(value) ? value : []
}

function capabilityForProvider(providerCode: string) {
  if (providerCode.includes('ocr') || providerCode === 'tesseract_ocr') return 'ocr'
  if (providerCode.includes('vision') || providerCode === 'mimo_2_5') return 'fault_scene_analysis'
  if (providerCode.includes('safety')) return 'safety_review'
  return 'text_chat'
}

function setError(err: unknown, fallback: string) {
  error.value = err instanceof Error ? err.message : fallback
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(async () => {
  await refreshAll()
  if (selectedMediaId.value) await loadSelectedMediaContext()
})
</script>
