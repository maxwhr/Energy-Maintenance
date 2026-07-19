<template>
  <PageFrame
    data-testid="multimodal-maintenance-page"
    title="多模态设备检修工作台"
    code="MULTIMODAL / MAINTENANCE"
    description="将用户描述、媒体、OCR、视觉区域和中文官方手册组织为可追溯证据链；识别结果不会自动成为确认事实。"
  >
    <template #actions>
      <span class="rounded border border-amber-300/30 bg-amber-400/10 px-3 py-2 text-xs font-bold text-amber-100">
        Dedicated Rerank: Deferred
      </span>
      <button class="scada-button" type="button" :disabled="busy" @click="refreshCases">刷新案例</button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100">{{ error }}</div>

    <div class="grid gap-4 2xl:grid-cols-[360px_minmax(0,1fr)]">
      <div class="space-y-4">
        <DataPanel title="1-3. 新建检修案例" subtitle="问题、设备和发生条件均进入案例证据链。">
          <form class="grid gap-3" data-testid="multimodal-case-create" @submit.prevent="createCase">
            <input v-model.trim="createForm.title" class="scada-input" placeholder="案例标题" :disabled="isViewer" />
            <textarea v-model.trim="createForm.user_query" class="scada-input min-h-24" placeholder="请描述现象、时间、告警和已执行操作" :disabled="isViewer"></textarea>
            <select v-model="createForm.device_id" class="scada-input" :disabled="isViewer">
              <option value="">不绑定设备</option>
              <option v-for="device in devices" :key="device.id" :value="device.id">
                {{ device.device_name }} / {{ device.model || device.product_series || '-' }}
              </option>
            </select>
            <div class="grid grid-cols-2 gap-2">
              <input v-model.trim="createForm.device_model" class="scada-input" placeholder="人工已知型号（可选）" :disabled="isViewer" />
              <select v-model="createForm.equipment_category" class="scada-input" :disabled="isViewer">
                <option value="">设备类别待确认</option>
                <option value="pv_inverter">光伏逆变器</option>
                <option value="battery_system">储能系统</option>
                <option value="smart_logger">SmartLogger</option>
                <option value="monitoring_platform">监控平台</option>
              </select>
            </div>
            <input v-model.trim="createForm.condition" class="scada-input" placeholder="发生条件：并网/夜间/升级后等" :disabled="isViewer" />
            <button class="scada-button primary" type="submit" :disabled="isViewer || busy || !createForm.title">新建案例</button>
            <p v-if="isViewer" class="text-xs text-amber-100">viewer 仅可查看，不能创建或修改案例。</p>
          </form>
        </DataPanel>

        <DataPanel title="案例列表" :subtitle="`共 ${casePage.total} 个案例`">
          <div class="max-h-[560px] space-y-2 overflow-auto pr-1">
            <button
              v-for="item in casePage.items"
              :key="item.case_id"
              type="button"
              class="w-full rounded border p-3 text-left"
              :class="activeCase?.case_id === item.case_id ? 'border-cyan-300/60 bg-cyan-400/10' : 'border-slate-600/20 bg-black/20'"
              @click="selectCase(item.case_id)"
            >
              <div class="flex items-start justify-between gap-2">
                <span class="font-black text-white">{{ item.title }}</span>
                <StatusTag :value="item.status" />
              </div>
              <div class="mt-2 line-clamp-2 text-xs text-slate-400">{{ item.user_query || '仅图片案例' }}</div>
              <div class="mt-2 text-[11px] text-slate-500">{{ item.case_id }}</div>
            </button>
            <EmptyState v-if="!casePage.items.length" text="暂无多模态检修案例" />
          </div>
        </DataPanel>
      </div>

      <div v-if="activeCase" class="space-y-4">
        <DataPanel title="案例状态与实体解析" subtitle="未确认的 OCR/视觉候选不会覆盖用户确认事实。">
          <div class="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
            <Metric label="状态" :value="activeCase.status" />
            <Metric label="设备型号" :value="activeCase.device_model || '待确认'" />
            <Metric label="产品族" :value="activeCase.product_family || '待确认'" />
            <Metric label="设备类别" :value="activeCase.equipment_category || '待确认'" />
            <Metric label="置信状态" :value="activeCase.confidence_status" />
            <Metric label="安全等级" :value="activeCase.safety_level" />
          </div>
          <div class="mt-3 grid gap-3 lg:grid-cols-4">
            <TokenList title="8. 识别型号" :items="modelCandidates" empty="暂无型号候选" />
            <TokenList title="9. 识别告警" :items="alarmCandidates" empty="暂无告警候选" />
            <TokenList title="10. 识别部件" :items="componentCandidates" empty="暂无部件候选" />
            <TokenList title="11. 指示灯状态" :items="indicatorCandidates" empty="暂无指示灯候选" />
          </div>
        </DataPanel>

        <div class="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,.75fr)]">
          <DataPanel title="4-7. 图片、OCR 与视觉区域" subtitle="边框颜色区分 OCR 观察与视觉推断；点击区域可定位证据。">
            <div v-if="selectedMedia" class="relative overflow-hidden rounded border border-slate-600/30 bg-black/30">
              <img v-if="previewUrl" :src="previewUrl" class="max-h-[560px] w-full object-contain" alt="案例媒体预览" />
              <div
                v-for="region in visibleRegions"
                :key="region.evidence_id"
                class="absolute cursor-pointer border-2"
                :class="region.modality === 'OCR_TEXT' ? 'border-cyan-300 bg-cyan-300/10' : 'border-violet-300 bg-violet-300/10'"
                :style="regionStyle(region)"
                :title="region.observed_text || region.evidence_type"
                @click="selectedEvidenceId = region.evidence_id"
              ></div>
            </div>
            <EmptyState v-else text="上传或选择一张案例图片后查看区域证据" />
            <div class="mt-3 flex flex-wrap gap-2">
              <button
                v-for="item in mediaItems"
                :key="item.media_id"
                type="button"
                class="rounded border px-3 py-2 text-xs"
                :class="selectedMediaId === item.media_id ? 'border-cyan-300 text-cyan-100' : 'border-slate-600/30 text-slate-300'"
                @click="selectMedia(item.media_id)"
              >
                {{ item.original_file_name || item.media_id }}
              </button>
            </div>
            <form class="mt-3 flex flex-wrap items-center gap-2" @submit.prevent="uploadMedia">
              <input data-testid="multimodal-media-upload" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" :disabled="isViewer" @change="onFile" />
              <select v-model="uploadForm.media_type" class="scada-input !w-auto" :disabled="isViewer">
                <option value="fault_image">故障图片</option>
                <option value="nameplate">铭牌</option>
                <option value="alarm_screen">告警屏幕</option>
                <option value="indicator_light">指示灯</option>
                <option value="site_photo">现场照片</option>
              </select>
              <button class="scada-button" type="submit" :disabled="isViewer || busy || !selectedFile">上传图片</button>
              <button class="scada-button primary" data-testid="multimodal-analyze" type="button" :disabled="isViewer || busy" @click="analyze">分析（安全 Dry-run）</button>
            </form>
          </DataPanel>

          <div class="space-y-4">
            <DataPanel title="12. 图片质量提示">
              <TokenList title="质量标记" :items="qualityFlags" empty="暂无质量问题" />
              <div class="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-300">
                <span>OCR ready: {{ selectedMedia?.ocr_ready ?? '-' }}</span>
                <span>Vision ready: {{ selectedMedia?.vision_ready ?? '-' }}</span>
              </div>
            </DataPanel>

            <DataPanel title="13. 证据冲突提示">
              <div v-for="conflict in conflicts" :key="conflict.conflict_id" class="mb-2 rounded border border-red-300/30 bg-red-400/10 p-3 text-sm">
                <div class="font-black text-red-100">{{ conflict.conflict_type }} / {{ conflict.severity }}</div>
                <div class="mt-1 text-xs text-red-100/80">{{ conflict.recommended_question || '需要人工核对' }}</div>
              </div>
              <EmptyState v-if="!conflicts.length" text="未检测到证据冲突" />
            </DataPanel>
          </div>
        </div>

        <DataPanel data-testid="multimodal-evidence-list" title="区域证据清单" subtitle="观察、模型推断、用户确认、低置信度和冲突状态独立显示。">
          <div class="grid gap-2 xl:grid-cols-2">
            <article
              v-for="item in evidenceItems"
              :key="item.evidence_id"
              class="rounded border p-3"
              :class="selectedEvidenceId === item.evidence_id ? 'border-cyan-300/60 bg-cyan-400/10' : 'border-slate-600/20 bg-black/20'"
              @click="selectedEvidenceId = item.evidence_id"
            >
              <div class="flex flex-wrap items-center gap-2">
                <EvidenceTag :value="item.observation_status" />
                <span class="text-xs font-bold text-slate-300">{{ item.modality }} / {{ item.evidence_type }}</span>
                <span class="ml-auto text-xs text-slate-400">{{ Math.round(item.confidence * 100) }}%</span>
              </div>
              <p class="mt-2 break-words text-sm text-white">{{ item.normalized_text || item.observed_text || summarizeVisual(item.visual_attributes) }}</p>
              <div class="mt-2 text-[11px] text-slate-500">region={{ item.region_id || '-' }} / source={{ item.source_type }}</div>
              <div v-if="!isViewer && !['USER_CONFIRMED', 'REJECTED'].includes(item.observation_status)" class="mt-3 flex flex-wrap gap-2">
                <button class="scada-button !min-h-8 !px-3" type="button" @click.stop="confirmEvidence(item.evidence_id)">确认</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click.stop="editEvidence(item)">修正确认</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click.stop="rejectEvidence(item.evidence_id)">识别错误</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click.stop="requestRetake(item.evidence_id)">要求重拍</button>
              </div>
            </article>
            <EmptyState v-if="!evidenceItems.length" text="尚未产生证据；分析不会自动调用真实 Provider" />
          </div>
        </DataPanel>

        <DataPanel title="14-15. 缺失信息、主动追问与用户补充">
          <div class="grid gap-3 lg:grid-cols-2">
            <TokenList title="缺失信息" :items="activeCase.missing_information" empty="暂无缺失信息" />
            <form class="grid gap-2" @submit.prevent="submitClarification">
              <label v-for="question in clarifyingQuestions" :key="question.question_id" class="grid gap-1 text-xs font-bold text-slate-300">
                {{ question.question }}
                <input v-model.trim="clarificationAnswers[question.question_id]" class="scada-input" :disabled="isViewer" placeholder="请补充事实，不要猜测" />
              </label>
              <button v-if="clarifyingQuestions.length" class="scada-button" type="submit" :disabled="isViewer || busy">提交补充信息</button>
              <EmptyState v-else text="当前无需主动追问" />
            </form>
          </div>
        </DataPanel>

        <div class="grid gap-4 xl:grid-cols-2">
          <DataPanel title="16. 检索查询">
            <div class="mb-3 flex flex-wrap gap-2">
              <button class="scada-button primary" data-testid="multimodal-retrieve" type="button" :disabled="isViewer || busy" @click="retrieve(false)">预览中文官方知识检索</button>
              <button class="scada-button" data-testid="multimodal-confirm-qa" type="button" :disabled="isViewer || busy || !retrieval?.citations?.length" @click="retrieve(true)">确认并保存 QA</button>
            </div>
            <div v-for="query in retrieval?.generated_queries || []" :key="query.query_type + query.query" class="mb-2 rounded bg-black/20 p-3 text-sm">
              <span class="font-bold text-cyan-100">{{ query.query_type }}</span>
              <span class="ml-2 text-slate-200">{{ query.query }}</span>
            </div>
            <div v-if="retrieval?.answer" class="mb-3 rounded border border-cyan-300/20 bg-cyan-400/10 p-3">
              <div class="text-xs font-black text-cyan-100">可追溯检修回答</div>
              <p class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-100">{{ retrieval.answer }}</p>
              <div class="mt-2 break-all text-[11px] text-slate-400">
                追溯编号 trace_id：{{ retrieval.trace_id || '-' }} · 记录状态：{{ retrieval.persistence_status || '-' }}
              </div>
            </div>
            <p class="text-xs text-slate-400">原始查询保留：{{ originalQueryRetained ? '是' : '待检索' }}；专用重排未调用。</p>
          </DataPanel>

          <DataPanel data-testid="multimodal-citations" title="17. 官方知识 Citation">
            <article v-for="citation in citations" :key="citation.chunk_id" class="mb-2 rounded border border-emerald-300/20 bg-emerald-400/10 p-3">
              <div class="text-xs font-black text-emerald-100">官方知识 · {{ citation.document_title || citation.document_id }}</div>
              <p class="mt-1 text-sm text-slate-200">{{ citation.quote || citation.section_title || '已验证原始手册定位' }}</p>
              <div class="mt-1 text-[11px] text-slate-400">chunk={{ citation.chunk_id }} / page={{ citation.page_number ?? '-' }}</div>
            </article>
            <EmptyState v-if="!citations.length" text="尚无可验证的官方知识引用" />
          </DataPanel>
        </div>

        <DataPanel title="18-21. 诊断可能性、支持/反对证据与安全警告">
          <div class="mb-3 flex flex-wrap gap-2">
            <button class="scada-button primary" data-testid="multimodal-diagnose" type="button" :disabled="isViewer || busy" @click="diagnose">生成证据约束诊断</button>
            <span class="rounded border border-amber-300/30 px-3 py-2 text-xs text-amber-100">无 Citation 时必须拒答</span>
          </div>
          <div class="grid gap-3 xl:grid-cols-2">
            <article v-for="item in diagnosis?.possible_faults || []" :key="item.hypothesis_id" class="rounded border border-slate-600/20 bg-black/20 p-4">
              <div class="flex items-center gap-2">
                <strong class="text-white">{{ item.fault_name }}</strong>
                <StatusTag :value="item.status" />
                <span class="ml-auto text-xs text-slate-400">{{ Math.round(item.confidence * 100) }}%</span>
              </div>
              <div class="mt-3 grid gap-2 md:grid-cols-2">
                <TokenList title="支持证据" :items="item.supporting_evidence_ids" empty="无" />
                <TokenList title="反对证据" :items="item.contradicting_evidence_ids" empty="无" />
              </div>
            </article>
          </div>
          <div class="mt-3 rounded border border-red-300/30 bg-red-400/10 p-4">
            <div class="font-black text-red-100">安全警告</div>
            <ul class="mt-2 list-disc space-y-1 pl-5 text-sm text-red-50">
              <li v-for="warning in safetyWarnings" :key="warning">{{ warning }}</li>
            </ul>
          </div>
        </DataPanel>

        <div class="grid gap-4 xl:grid-cols-2">
          <DataPanel title="22. SOP 草稿" subtitle="只生成待审核 Agent Artifact，绝不自动批准。">
            <button class="scada-button" type="button" :disabled="isViewer || busy" @click="createSop">生成 SOP 草稿</button>
            <pre v-if="sopDraft" class="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-black/20 p-3 text-xs text-slate-200">{{ draftText(sopDraft) }}</pre>
            <p class="mt-2 text-xs text-amber-100">automatic approval = 0</p>
          </DataPanel>
          <DataPanel title="23. Task 草稿" subtitle="不创建正式 MaintenanceTask，不自动派单。">
            <label class="mb-3 flex items-center gap-2 text-xs text-slate-300">
              <input v-model="sopUserConfirmed" type="checkbox" :disabled="isViewer" />
              我已人工确认 SOP 草稿可用于创建任务草稿
            </label>
            <button class="scada-button" type="button" :disabled="isViewer || busy || !sopUserConfirmed" @click="createTask">生成 Task 草稿</button>
            <pre v-if="taskDraft" class="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-black/20 p-3 text-xs text-slate-200">{{ draftText(taskDraft) }}</pre>
            <p class="mt-2 text-xs text-amber-100">automatic formal task = 0</p>
          </DataPanel>
        </div>

        <DataPanel title="24. 审计时间线" subtitle="从用户输入、媒体、证据、检索到草稿的全部关键动作均留痕。">
          <ol class="space-y-2 border-l border-cyan-300/30 pl-4">
            <li v-for="item in audits" :key="item.id" class="relative rounded bg-black/20 p-3 text-sm">
              <span class="absolute -left-[21px] top-4 h-2 w-2 rounded-full bg-cyan-300"></span>
              <div class="font-black text-white">{{ item.action }}</div>
              <div class="mt-1 text-xs text-slate-400">{{ formatTime(item.created_at) }} / {{ item.operator || '-' }}</div>
            </li>
          </ol>
          <EmptyState v-if="!audits.length" text="暂无审计事件" />
        </DataPanel>
      </div>

      <DataPanel v-else title="多模态检修案例">
        <EmptyState text="请选择已有案例，或由 engineer/expert/admin 创建新案例" />
      </DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  analyzeMultimodalCase,
  clarifyMultimodalCase,
  confirmMultimodalEvidence,
  createMultimodalCase,
  createMultimodalSopDraft,
  createMultimodalTaskDraft,
  diagnoseMultimodalCase,
  getDevicesApi,
  getMediaContentApi,
  getMultimodalCase,
  getMultimodalCaseAudit,
  getMultimodalCaseEvidence,
  getMultimodalCaseMedia,
  getMultimodalCases,
  rejectMultimodalEvidence,
  retrieveMultimodalCase,
  uploadMultimodalCaseMedia
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import { useUserStore } from '@/stores/user'
import type { DeviceItem } from '@/types'
import type {
  MultimodalAuditItem,
  MultimodalCaseMedia,
  MultimodalClarifyingQuestion,
  MultimodalConflict,
  MultimodalDiagnosisResult,
  MultimodalDraftResult,
  MultimodalEvidenceItem,
  MultimodalMaintenanceCase,
  MultimodalRetrievalResult
} from '@/types/multimodalMaintenance'

const StatusTag = defineComponent({
  props: { value: { type: String, required: true } },
  setup(props) {
    return () => h('span', { class: 'rounded border border-cyan-300/30 bg-cyan-400/10 px-2 py-1 text-[10px] font-bold text-cyan-100' }, props.value)
  }
})

const EvidenceTag = defineComponent({
  props: { value: { type: String, required: true } },
  setup(props) {
    const labels: Record<string, string> = {
      OBSERVED: '已观察', INFERRED: '模型推断', USER_CONFIRMED: '用户确认', CONTRADICTED: '存在冲突',
      LOW_CONFIDENCE: '低置信度', REJECTED: '已拒绝'
    }
    return () => h('span', { class: 'rounded border border-slate-500/40 px-2 py-1 text-[10px] font-bold text-slate-100' }, labels[props.value] || props.value)
  }
})

const Metric = defineComponent({
  props: { label: { type: String, required: true }, value: { type: [String, Number], required: true } },
  setup(props) {
    return () => h('div', { class: 'rounded border border-slate-600/20 bg-black/20 p-3' }, [
      h('div', { class: 'text-[11px] font-bold text-slate-400' }, props.label),
      h('div', { class: 'mt-1 break-words text-sm font-black text-white' }, String(props.value))
    ])
  }
})

const TokenList = defineComponent({
  props: {
    title: { type: String, required: true },
    items: { type: Array as () => string[], required: true },
    empty: { type: String, required: true }
  },
  setup(props) {
    return () => h('div', { class: 'rounded border border-slate-600/20 bg-black/20 p-3' }, [
      h('div', { class: 'text-xs font-black text-slate-200' }, props.title),
      props.items.length
        ? h('div', { class: 'mt-2 flex flex-wrap gap-1' }, props.items.map((item) => h('span', { class: 'rounded bg-white/5 px-2 py-1 text-[11px] text-slate-200' }, item)))
        : h('div', { class: 'mt-2 text-xs text-slate-500' }, props.empty)
    ])
  }
})

const userStore = useUserStore()
const isViewer = computed(() => userStore.role === 'viewer')
const busy = ref(false)
const error = ref('')
const devices = ref<DeviceItem[]>([])
const casePage = reactive({ items: [] as MultimodalMaintenanceCase[], total: 0 })
const activeCase = ref<MultimodalMaintenanceCase | null>(null)
const mediaItems = ref<MultimodalCaseMedia[]>([])
const evidenceItems = ref<MultimodalEvidenceItem[]>([])
const conflicts = ref<MultimodalConflict[]>([])
const retrieval = ref<MultimodalRetrievalResult | null>(null)
const diagnosis = ref<MultimodalDiagnosisResult | null>(null)
const sopDraft = ref<MultimodalDraftResult | null>(null)
const taskDraft = ref<MultimodalDraftResult | null>(null)
const audits = ref<MultimodalAuditItem[]>([])
const selectedFile = ref<File | null>(null)
const selectedMediaId = ref('')
const selectedEvidenceId = ref('')
const previewUrl = ref('')
const sopUserConfirmed = ref(false)
const clarificationAnswers = reactive<Record<string, string>>({})
const createForm = reactive({ title: '', user_query: '', device_id: '', device_model: '', equipment_category: '', condition: '' })
const uploadForm = reactive({ media_type: 'fault_image' })

const selectedMedia = computed(() => mediaItems.value.find((item) => item.media_id === selectedMediaId.value) || null)
const visibleRegions = computed(() => evidenceItems.value.filter((item) => item.media_id === selectedMediaId.value && item.bounding_box))
const modelCandidates = computed(() => unique(evidenceItems.value.flatMap((item) => item.device_model_candidates)))
const alarmCandidates = computed(() => unique([...(activeCase.value?.alarm_codes || []), ...evidenceItems.value.flatMap((item) => item.alarm_code_candidates)]))
const componentCandidates = computed(() => unique([...(activeCase.value?.components || []), ...evidenceItems.value.flatMap((item) => item.component_candidates)]))
const indicatorCandidates = computed(() => unique(evidenceItems.value.flatMap((item) => item.indicator_state_candidates)))
const qualityFlags = computed(() => selectedMedia.value?.quality_flags || [])
const citations = computed(() => diagnosis.value?.citations || retrieval.value?.citations || activeCase.value?.knowledge_citations || [])
const safetyWarnings = computed(() => diagnosis.value?.safety_warnings?.length
  ? diagnosis.value.safety_warnings
  : ['在完成停机、隔离、验电和防护确认前，不执行带电拆装或高风险操作。'])
const clarifyingQuestions = computed<MultimodalClarifyingQuestion[]>(() => (activeCase.value?.clarifying_questions || [])
  .map((item, index) => typeof item === 'string'
    ? { question_id: `question_${index}`, question_type: 'GENERAL', question: item, required: true, safe_template: true }
    : item))
const originalQueryRetained = computed(() => Boolean(retrieval.value?.generated_queries.some((item) => item.query_type === 'ORIGINAL_TEXT')))

function unique(items: string[]) { return [...new Set(items.filter(Boolean))] }
function setError(err: unknown, fallback: string) { error.value = err instanceof Error ? err.message : fallback }
function formatTime(value?: string | null) { return value ? new Date(value).toLocaleString('zh-CN') : '-' }
function summarizeVisual(value: Record<string, unknown>) { return Object.keys(value).length ? JSON.stringify(value) : '结构化区域证据' }
function draftText(value: MultimodalDraftResult) { return JSON.stringify(value.artifact?.content || value.boundary, null, 2) }

function normalizedBox(item: MultimodalEvidenceItem) {
  const box = item.bounding_box
  if (Array.isArray(box) && box.length >= 4) return { x1: box[0], y1: box[1], x2: box[2], y2: box[3] }
  if (box && !Array.isArray(box)) return { x1: box.x1 ?? box.x ?? 0, y1: box.y1 ?? box.y ?? 0, x2: box.x2 ?? ((box.x ?? 0) + (box.width ?? 0)), y2: box.y2 ?? ((box.y ?? 0) + (box.height ?? 0)) }
  return { x1: 0, y1: 0, x2: 0, y2: 0 }
}

function regionStyle(item: MultimodalEvidenceItem) {
  const box = normalizedBox(item)
  const locator = item.page_or_frame_locator || {}
  const width = Number(locator.image_width || locator.width || 1)
  const height = Number(locator.image_height || locator.height || 1)
  const normalized = Math.max(box.x2, box.y2) <= 1
  const left = normalized ? box.x1 * 100 : box.x1 / width * 100
  const top = normalized ? box.y1 * 100 : box.y1 / height * 100
  const regionWidth = normalized ? (box.x2 - box.x1) * 100 : (box.x2 - box.x1) / width * 100
  const regionHeight = normalized ? (box.y2 - box.y1) * 100 : (box.y2 - box.y1) / height * 100
  return { left: `${left}%`, top: `${top}%`, width: `${Math.max(regionWidth, 1)}%`, height: `${Math.max(regionHeight, 1)}%` }
}

async function refreshCases() {
  busy.value = true; error.value = ''
  try {
    const result = await getMultimodalCases({ page: 1, page_size: 100 })
    casePage.items = result.items; casePage.total = result.total
    if (!activeCase.value && result.items[0]) await selectCase(result.items[0].case_id)
  } catch (err) { setError(err, '案例读取失败') } finally { busy.value = false }
}

async function createCase() {
  if (isViewer.value) return
  busy.value = true; error.value = ''
  try {
    const item = await createMultimodalCase({
      title: createForm.title,
      user_query: createForm.user_query || null,
      device_id: createForm.device_id || null,
      device_model: createForm.device_model || null,
      equipment_category: createForm.equipment_category || null,
      occurrence_conditions: createForm.condition ? [createForm.condition] : [],
      idempotency_key: crypto.randomUUID()
    })
    createForm.title = ''; createForm.user_query = ''; createForm.condition = ''
    await refreshCases(); await selectCase(item.case_id)
  } catch (err) { setError(err, '案例创建失败') } finally { busy.value = false }
}

async function selectCase(caseId: string) {
  error.value = ''
  try {
    activeCase.value = await getMultimodalCase(caseId)
    retrieval.value = null; diagnosis.value = null; sopDraft.value = null; taskDraft.value = null
    await Promise.all([loadMedia(), loadEvidence(), loadAudit()])
  } catch (err) { setError(err, '案例详情读取失败') }
}

async function loadMedia() {
  if (!activeCase.value) return
  const result = await getMultimodalCaseMedia(activeCase.value.case_id)
  mediaItems.value = result.items
  const next = mediaItems.value.some((item) => item.media_id === selectedMediaId.value) ? selectedMediaId.value : mediaItems.value[0]?.media_id || ''
  await selectMedia(next)
}

async function selectMedia(mediaId: string) {
  selectedMediaId.value = mediaId
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  if (!mediaId) return
  try { previewUrl.value = URL.createObjectURL(await getMediaContentApi(mediaId)) } catch { previewUrl.value = '' }
}

async function loadEvidence() {
  if (!activeCase.value) return
  const result = await getMultimodalCaseEvidence(activeCase.value.case_id)
  evidenceItems.value = result.items; conflicts.value = result.conflicts
}

async function loadAudit() {
  if (!activeCase.value) return
  const result = await getMultimodalCaseAudit(activeCase.value.case_id)
  audits.value = result.items
}

function onFile(event: Event) { selectedFile.value = (event.target as HTMLInputElement).files?.[0] || null }

async function uploadMedia() {
  if (!activeCase.value || !selectedFile.value || isViewer.value) return
  busy.value = true; error.value = ''
  try {
    const form = new FormData(); form.append('file', selectedFile.value); form.append('media_type', uploadForm.media_type)
    form.append('device_type', activeCase.value.equipment_category || 'unknown')
    if (activeCase.value.product_family) form.append('product_series', activeCase.value.product_family)
    await uploadMultimodalCaseMedia(activeCase.value.case_id, form)
    selectedFile.value = null; await selectCase(activeCase.value.case_id)
  } catch (err) { setError(err, '图片上传失败') } finally { busy.value = false }
}

async function analyze() { await action(async () => { if (activeCase.value) await analyzeMultimodalCase(activeCase.value.case_id) }, '分析请求失败') }
async function retrieve(persistResult = false) {
  await action(async () => {
    if (!activeCase.value) return
    const requestId = `task30a-mm-${activeCase.value.case_id}`
    retrieval.value = await retrieveMultimodalCase(activeCase.value.case_id, persistResult, requestId)
  }, persistResult ? 'QA 确认保存失败' : '跨模态检索预览失败')
}
async function diagnose() { await action(async () => { if (activeCase.value) diagnosis.value = await diagnoseMultimodalCase(activeCase.value.case_id) }, '诊断失败') }
async function createSop() { await action(async () => { if (activeCase.value) sopDraft.value = await createMultimodalSopDraft(activeCase.value.case_id) }, 'SOP 草稿生成失败') }
async function createTask() { await action(async () => { if (activeCase.value) taskDraft.value = await createMultimodalTaskDraft(activeCase.value.case_id, sopUserConfirmed.value) }, 'Task 草稿生成失败') }

async function confirmEvidence(evidenceId: string) { await action(async () => { if (activeCase.value) await confirmMultimodalEvidence(activeCase.value.case_id, evidenceId); await loadEvidence() }, '证据确认失败') }
async function rejectEvidence(evidenceId: string) { await action(async () => { if (activeCase.value) await rejectMultimodalEvidence(activeCase.value.case_id, evidenceId); await loadEvidence() }, '证据拒绝失败') }

async function editEvidence(item: MultimodalEvidenceItem) {
  const current = item.normalized_text || item.observed_text || ''
  const value = window.prompt('请输入人工核对后的内容', current)
  if (value === null || !value.trim()) return
  await action(async () => {
    if (activeCase.value) await confirmMultimodalEvidence(activeCase.value.case_id, item.evidence_id, value.trim())
    await loadEvidence()
  }, '证据修正确认失败')
}

async function requestRetake(evidenceId: string) {
  await action(async () => {
    if (activeCase.value) await rejectMultimodalEvidence(activeCase.value.case_id, evidenceId, 'request_retake: 图片信息不足，请按安全要求重新拍摄')
    await loadEvidence()
  }, '重拍请求提交失败')
}

async function submitClarification() {
  if (!activeCase.value || isViewer.value) return
  const answers = Object.fromEntries(Object.entries(clarificationAnswers).filter(([, value]) => value.trim()))
  if (!Object.keys(answers).length) return
  await action(async () => { if (activeCase.value) activeCase.value = await clarifyMultimodalCase(activeCase.value.case_id, answers) }, '补充信息提交失败')
}

async function action(fn: () => Promise<void>, fallback: string) {
  if (isViewer.value) return
  busy.value = true; error.value = ''
  try { await fn(); if (activeCase.value) { activeCase.value = await getMultimodalCase(activeCase.value.case_id); await loadAudit() } }
  catch (err) { setError(err, fallback) } finally { busy.value = false }
}

onMounted(async () => {
  try { devices.value = (await getDevicesApi({ page: 1, page_size: 100 })).items } catch { devices.value = [] }
  await refreshCases()
})
onBeforeUnmount(() => { if (previewUrl.value) URL.revokeObjectURL(previewUrl.value) })
</script>
