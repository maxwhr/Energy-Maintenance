<template>
  <PageFrame
    title="华为 SUN2000 光伏逆变器检修知识检索"
    code="HUAWEI SUN2000 / SOURCE TRACE"
    description="输入型号、告警代码或故障现象，系统仅在已审核的华为 SUN2000 与直接相关 FusionSolar 中文资料中检索并返回可追溯回答。"
  >
    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="检索问题" subtitle="原始问题始终保留；模型只辅助理解，不直接诊断。">
        <form class="grid gap-3" data-testid="query-aware-form" @submit.prevent="submit">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            问题
            <textarea
              v-model.trim="form.query"
              class="scada-input min-h-32"
              placeholder="例如：华为 SUN2000-100KTL-M1 绝缘阻抗低如何排查？"
              required
            />
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              检索模式
              <select v-model="form.retrieval_mode" class="scada-input">
                <option value="auto">自动</option>
                <option value="fast">快速关键词检索</option>
                <option value="deep">深度多查询</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              返回结果
              <input v-model.number="form.top_k" class="scada-input" min="1" max="10" type="number" />
            </label>
          </div>
          <div class="rounded border border-cyan-300/20 bg-cyan-400/10 p-3 text-xs leading-5 text-cyan-100">
            正式范围：华为 SUN2000 光伏逆变器及直接相关 FusionSolar 检修资料。阳光电源、LUNA2000、独立 SmartLogger、待审核及归档资料不参与检索。
          </div>
          <button class="scada-button primary" type="submit" :disabled="loading">
            <SearchIcon :size="16" />
            {{ loading ? '正在检索正式知识库' : '检索检修知识' }}
          </button>
        </form>

        <details v-if="result" class="mt-4 rounded border border-cyan-300/20 bg-black/20 p-3 text-xs" data-testid="r5-r5-diagnostics">
          <summary class="cursor-pointer font-bold text-cyan-100">查询识别摘要（调试）</summary>
          <div class="mt-3 grid gap-2">
            <div data-testid="primary-intent">主要意图：<span class="font-mono text-cyan-200">{{ result.primary_intent }}</span></div>
            <div data-testid="requested-information">请求信息：<span class="font-mono text-cyan-200">{{ (result.requested_information || []).join(' / ') || '-' }}</span></div>
            <div data-testid="composite-intent">复合意图：<span class="text-cyan-200">{{ (result.requested_information || []).length > 1 ? '是' : '否' }}</span></div>
            <div data-testid="anchor-coverage">锚点覆盖：<span class="text-cyan-200">{{ (result.retrieval_plan?.anchor_types || []).join(' / ') || '-' }}</span></div>
            <div data-testid="anchor-matrix-version">锚点矩阵：<span class="font-mono text-cyan-200">{{ result.retrieval_plan?.anchor_matrix_version || '-' }}</span></div>
            <div data-testid="citation-validation">引用有效率 / 覆盖率：<span class="text-cyan-200">{{ percent(result.citation_validity_ratio) }} / {{ percent(result.citation_coverage_ratio) }}</span></div>
            <div data-testid="confidence-status">证据状态：<span class="font-mono text-cyan-200">{{ result.confidence_status }}</span></div>
          </div>
        </details>

        <div v-if="result?.needs_clarification" class="mt-4 grid gap-3 rounded border border-amber-300/30 bg-amber-400/10 p-4" data-testid="clarification-panel">
          <div class="text-sm font-black text-amber-100">需要补充信息</div>
          <p class="text-sm leading-6 text-amber-50">{{ result.clarifying_question }}</p>
          <div class="text-xs text-amber-200">缺失：{{ (result.missing_information || []).join(' / ') || '-' }}</div>
          <textarea v-model.trim="clarification" class="scada-input min-h-20" placeholder="补充型号、告警码或具体症状" />
          <button class="scada-button" type="button" :disabled="loading || !clarification" @click="submitClarification">
            提交补充信息并重新检索
          </button>
        </div>
      </DataPanel>

      <div class="space-y-4">
        <DataPanel v-if="result && !result.needs_clarification" title="检修回答与来源追溯" data-testid="formal-rag-answer">
          <div
            class="rounded border p-3 text-sm"
            :class="result.confidence_status === 'UNSUPPORTED_SCOPE'
              ? 'border-amber-300/30 bg-amber-400/10 text-amber-100'
              : result.abstained
                ? 'border-slate-400/30 bg-slate-400/10 text-slate-200'
                : 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100'"
          >
            {{ result.message }}
          </div>
          <div v-if="result.persistence_status === 'failed'" class="mt-3 rounded border border-red-300/30 bg-red-400/10 p-3 text-sm text-red-100">
            回答已生成，但问答记录未保存。请稍后重试，当前页面不会将其标记为已归档。
          </div>
          <div class="mt-3 grid gap-3 md:grid-cols-4">
            <div class="rounded bg-white/[0.03] p-3 text-xs"><span class="text-slate-400">厂家</span><p class="mt-1 text-white">华为 Huawei</p></div>
            <div class="rounded bg-white/[0.03] p-3 text-xs"><span class="text-slate-400">产品系列</span><p class="mt-1 text-white">{{ result.query_signals?.product_family || 'SUN2000' }}</p></div>
            <div class="rounded bg-white/[0.03] p-3 text-xs"><span class="text-slate-400">识别型号</span><p class="mt-1 font-mono text-cyan-200">{{ result.query_signals?.model || '未指定' }}</p></div>
            <div class="rounded bg-white/[0.03] p-3 text-xs"><span class="text-slate-400">告警 / 故障</span><p class="mt-1 text-white">{{ result.query_signals?.alarm_code || result.query_signals?.fault_type || '未指定' }}</p></div>
          </div>
          <div class="mt-4 rounded border border-white/10 bg-black/20 p-4">
            <div class="text-xs font-bold text-cyan-200">初步检修建议</div>
            <p class="mt-2 whitespace-pre-line text-sm leading-7 text-slate-100">{{ result.answer }}</p>
          </div>
          <div class="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <div class="mb-2 text-sm font-black text-white">建议步骤</div>
              <ol v-if="result.suggested_steps?.length" class="space-y-2 text-sm text-slate-200">
                <li v-for="(step, index) in result.suggested_steps" :key="`${index}-${step}`" class="rounded bg-white/[0.03] p-3">
                  {{ Number(index) + 1 }}. {{ step }}
                </li>
              </ol>
              <EmptyState v-else text="当前正式知识范围没有足够证据生成具体步骤。" />
            </div>
            <div>
              <div class="mb-2 text-sm font-black text-white">安全提醒</div>
              <ul class="space-y-2 text-sm text-amber-100">
                <li v-for="(note, index) in result.safety_notes || []" :key="`${index}-${note}`" class="rounded border border-amber-300/20 bg-amber-400/10 p-3">
                  {{ note }}
                </li>
              </ul>
            </div>
          </div>
          <div class="mt-4 grid gap-2 border-t border-white/10 pt-3 text-xs text-slate-400 md:grid-cols-2">
            <span>回答置信度：<strong class="text-cyan-200">{{ percent(result.confidence) }}</strong></span>
            <span>记录状态：<strong class="text-cyan-200">{{ persistenceLabel }}</strong></span>
            <span>追溯编号 trace_id：<code class="text-slate-200">{{ result.trace_id || '-' }}</code></span>
            <span>请求编号 request_id：<code class="text-slate-200">{{ result.request_id }}</code></span>
          </div>
        </DataPanel>

        <DataPanel title="问题理解" data-testid="query-understanding-panel">
          <EmptyState v-if="!result" text="提交问题后显示标准化问题、意图、缺失信息和检索证据。" />
          <div v-else class="space-y-3 text-sm">
            <div class="grid gap-3 md:grid-cols-2">
              <div class="rounded bg-white/[0.03] p-3"><span class="text-slate-400">原始问题</span><p class="mt-1 text-white">{{ result.original_query }}</p></div>
              <div class="rounded bg-white/[0.03] p-3" data-testid="canonical-question"><span class="text-slate-400">标准化问题</span><p class="mt-1 text-white">{{ result.canonical_question }}</p></div>
              <div class="rounded bg-white/[0.03] p-3"><span class="text-slate-400">主要意图</span><p class="mt-1 font-mono text-cyan-200">{{ result.primary_intent }}</p></div>
              <div class="rounded bg-white/[0.03] p-3"><span class="text-slate-400">理解路径</span><p class="mt-1 text-white">{{ understandingModeLabel }}</p></div>
              <div class="rounded bg-white/[0.03] p-3"><span class="text-slate-400">结构化输出</span><p class="mt-1 text-white">{{ result.structured_model_diagnostics?.query_understanding?.success ? '成功' : (result.query_understanding_fallback ? '安全 fallback' : '未调用') }}</p></div>
              <div class="rounded bg-white/[0.03] p-3"><span class="text-slate-400">确定性重排</span><p class="mt-1 text-white">{{ result.deterministic_rerank?.candidates_in ? (result.deterministic_rerank?.order_changed ? '已执行并调整顺序' : '已执行，顺序保持') : 'Fast Path 跳过' }}</p></div>
              <div class="rounded bg-white/[0.03] p-3"><span class="text-slate-400">Qwen3 专用重排</span><p class="mt-1 text-white">{{ dedicatedRerankLabel }}</p></div>
            </div>
            <div class="rounded border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
              已确认事实：{{ factSummary }}<br />
              完整性：{{ result.needs_clarification ? '需要追问' : (result.missing_information || []).length ? '部分完整' : '清晰' }}；歧义：{{ result.ambiguity ? '是' : '否' }}
            </div>
          </div>
        </DataPanel>

        <details v-if="result && !result.needs_clarification" class="rounded border border-white/10 bg-black/10 p-3">
          <summary class="cursor-pointer text-sm font-bold text-slate-300">高级检索诊断（演示与调试）</summary>
          <div class="mt-3 space-y-4">
        <DataPanel title="检索计划与证据状态" data-testid="retrieval-plan-panel">
          <div class="grid gap-3 text-xs md:grid-cols-3">
            <div class="rounded bg-white/[0.03] p-3">请求通道<br /><span class="text-cyan-200">{{ (result.requested_channels || []).join(' / ') || '-' }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">实际通道<br /><span class="text-cyan-200">{{ (result.actual_channels || []).join(' / ') || '-' }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">执行/非空通道<br /><span class="text-cyan-200">{{ (result.executed_channels || []).join(' / ') || '-' }} / {{ (result.nonempty_channels || []).join(' / ') || '-' }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">RAW_VECTOR<br /><span class="text-cyan-200">{{ rawVectorSummary }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">Rerank<br /><span class="text-cyan-200">{{ result.rerank_used ? (result.rerank_fallback ? 'fallback' : 'executed') : 'skipped' }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">证据状态<br /><span class="font-mono text-cyan-200">{{ result.confidence_status }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">置信度<br /><span class="text-cyan-200">{{ percent(result.retrieval_confidence) }}</span></div>
            <div class="rounded bg-white/[0.03] p-3">R5 Partition<br /><span class="font-mono text-cyan-200">{{ result.partition }}</span></div>
          </div>
          <div class="mt-3 rounded border border-white/10 bg-black/20 p-3 text-xs" data-testid="generated-queries">
            <div class="mb-2 font-bold text-slate-300">多查询路线（{{ (result.generated_queries || []).length }}）</div>
            <ol class="space-y-1 text-slate-400">
              <li v-for="(query, index) in result.generated_queries || []" :key="`${query}-${index}`">{{ Number(index) + 1 }}. {{ query }}</li>
            </ol>
          </div>
          <div class="mt-3 rounded border border-violet-300/20 bg-violet-400/10 p-3 text-xs" data-testid="dedicated-rerank-diagnostics">
            <div class="grid gap-2 md:grid-cols-4">
              <span>专用 Rerank：{{ result.dedicated_rerank?.used ? 'used' : 'not used' }}</span>
              <span>模型：{{ result.dedicated_rerank?.model || '-' }}</span>
              <span>Provider：{{ result.dedicated_rerank?.provider_status || '-' }}</span>
              <span>Fallback：{{ result.dedicated_rerank?.fallback ? (result.dedicated_rerank?.fallback_reason || 'yes') : 'no' }}</span>
              <span>耗时：{{ decimal(result.dedicated_rerank?.latency_ms) }} ms</span>
              <span>缓存：{{ result.dedicated_rerank?.cache_hit ? 'hit' : 'miss' }}</span>
              <span>熔断：{{ result.dedicated_rerank?.circuit_breaker_state || '-' }}</span>
              <span>约束：{{ result.post_rerank_constraints?.status || '-' }}</span>
            </div>
            <div v-if="(result.dedicated_rerank?.rankings || []).length" class="mt-3 overflow-x-auto">
              <table class="w-full min-w-[620px] text-left">
                <thead class="text-slate-400"><tr><th>候选</th><th>重排前</th><th>重排后</th><th>分数</th><th>状态</th></tr></thead>
                <tbody><tr v-for="item in result.dedicated_rerank.rankings" :key="item.candidate_id" class="border-t border-white/10">
                  <td class="py-1 font-mono">{{ shortId(item.candidate_id) }}</td><td>{{ item.pre_rerank_rank }}</td><td>{{ item.rerank_rank }}</td><td>{{ decimal(item.rerank_score) }}</td><td>{{ item.provider_status }}</td>
                </tr></tbody>
              </table>
            </div>
          </div>
        </DataPanel>

        <DataPanel title="有据回答边界" data-testid="answer-boundary-panel">
          <div v-if="result.answer_boundary?.insufficient_evidence_notice" class="rounded border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">
            {{ result.answer_boundary.insufficient_evidence_notice }}
          </div>
          <div v-else-if="result.confidence_status === 'MULTIPLE_POSSIBILITIES'" class="rounded border border-violet-300/30 bg-violet-400/10 p-3 text-sm text-violet-100">
            当前有多种可能，以下内容均为官方原文证据候选，不作为确定性诊断。
          </div>
          <div v-else class="rounded border border-emerald-300/30 bg-emerald-400/10 p-3 text-sm text-emerald-100">
            已找到可引用的官方中文证据；现场操作仍需遵循安全规程并由人员确认。
          </div>
          <div class="mt-3 text-xs text-slate-400">
            候选假设提升为事实：{{ result.answer_boundary?.hypotheses_promoted_to_fact ? '是' : '否' }} ·
            无证据维修指令：{{ result.answer_boundary?.unsupported_repair_instructions ?? 0 }}
          </div>
        </DataPanel>
          </div>
        </details>

        <DataPanel v-if="result && !result.needs_clarification" title="正式知识来源" data-testid="citation-panel">
          <div v-if="formalReferences.length" class="grid gap-3">
            <article v-for="citation in formalReferences" :key="citation.chunk_id" class="rounded border border-white/10 bg-black/20 p-4 text-sm">
              <div class="font-black text-white">{{ citation.document_title }}</div>
              <div class="mt-1 text-xs text-cyan-200">
                {{ citation.source_type || citation.document_type || '正式资料' }} · {{ citation.section_title || '未标注章节' }}
                <template v-if="citation.page_number"> · 第 {{ citation.page_number }} 页</template>
                · Chunk {{ citation.chunk_index ?? '-' }}
              </div>
              <p class="mt-2 text-xs leading-6 text-slate-300">{{ citation.quote }}</p>
              <div class="mt-2 text-[11px] text-slate-500">来源：{{ citation.source || '-' }} · 分数 {{ decimal(citation.score) }} · ID {{ shortId(citation.chunk_id) }}</div>
            </article>
          </div>
          <EmptyState v-else text="当前知识库未检索到足够相关且通过范围校验的华为 SUN2000 资料。" />
          <div v-if="(result.invalid_citations || []).length" class="mt-3 rounded border border-amber-300/30 bg-amber-400/10 p-3 text-xs text-amber-100">
            {{ result.invalid_citations.length }} 条引用未通过逐条校验；合法引用仍保留。有效率 {{ percent(result.citation_validity_ratio) }}。
          </div>
        </DataPanel>

        <details v-if="(result?.surfaced_results || []).length" class="rounded border border-white/10 bg-black/10 p-3">
          <summary class="cursor-pointer text-sm font-bold text-slate-300">候选证据评分（调试）</summary>
          <div class="mt-3">
        <DataPanel title="候选证据评分">
          <div class="space-y-2 text-xs">
            <div v-for="item in result?.surfaced_results || []" :key="item.candidate_id" class="grid gap-1 rounded bg-white/[0.03] p-3 md:grid-cols-[1fr_auto]">
              <div><span class="font-bold text-white">{{ item.document_title }}</span><br /><span class="text-slate-400">{{ item.section_title || '-' }} · page {{ item.page_number ?? '-' }}</span></div>
              <div class="font-mono text-cyan-200">RRF {{ decimal(item.rrf_score) }} · Rerank {{ decimal(item.rerank_score) }} · Final {{ decimal(item.final_score) }}</div>
            </div>
          </div>
        </DataPanel>
          </div>
        </details>
      </div>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import axios from 'axios'
import { computed, onUnmounted, reactive, ref } from 'vue'
import { Search as SearchIcon } from '@lucide/vue'
import { clarifyRetrievalQueryApi, queryAwareRetrievalApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import type { QueryAwareRetrievalResponse } from '@/types'

const form = reactive<{ query: string; retrieval_mode: 'auto' | 'fast' | 'deep'; top_k: number }>({
  query: '',
  retrieval_mode: 'fast',
  top_k: 5
})
const result = ref<QueryAwareRetrievalResponse | null>(null)
const clarification = ref('')
const loading = ref(false)
const error = ref('')
let submitTimer: ReturnType<typeof setTimeout> | null = null
let activeController: AbortController | null = null
let activeRequestKey = ''

const factSummary = computed(() => {
  const facts = result.value?.confirmed_facts || {}
  const values = Object.entries(facts)
    .filter(([, value]) => Array.isArray(value) && value.length)
    .map(([key, value]) => `${key}: ${(value as unknown[]).join(', ')}`)
  return values.join('；') || '无可确认的显式事实'
})
const rawVectorSummary = computed(() => {
  const traces = Object.values(result.value?.raw_vector_trace || {}) as Record<string, any>[]
  if (!traces.length) return '未请求'
  return traces.some((item) => item.executed) ? `已执行，命中 ${traces.reduce((sum, item) => sum + Number(item.post_filter_hits || 0), 0)}` : '请求失败/回退'
})
const understandingModeLabel = computed(() => {
  const mode = result.value?.query_understanding_mode
  if (mode === 'MINIMAX_TOOL') return 'MiniMax-M3 Tool Calling'
  if (mode === 'FAST_PATH') return '确定性 Fast Path（无外部调用）'
  if (mode === 'SAFE_FALLBACK') return 'MiniMax 不可用，已安全降级'
  return '确定性标准化（无外部调用）'
})
const dedicatedRerankLabel = computed(() => {
  const value = result.value?.dedicated_rerank || {}
  if (value.used) return `${value.model || 'qwen3-rerank'} / success`
  if (value.fallback) return `fallback: ${value.fallback_reason || 'deterministic order'}`
  return '未启用'
})
const formalReferences = computed(() => result.value?.references || [])
const persistenceLabel = computed(() => {
  const status = result.value?.persistence_status
  if (status === 'persisted') return '已保存到问答记录'
  if (status === 'reused_idempotent_record') return '已复用原问答记录'
  if (status === 'skipped_preview') return '预览模式，未保存'
  if (status === 'failed') return '保存失败'
  if (status === 'not_persisted_clarification') return '等待补充信息'
  return status || '未请求保存'
})

function submit() {
  if (submitTimer) clearTimeout(submitTimer)
  submitTimer = setTimeout(() => {
    submitTimer = null
    void executeSubmit()
  }, 200)
}

async function executeSubmit() {
  const requestKey = JSON.stringify({
    query: form.query,
    retrieval_mode: form.retrieval_mode,
    top_k: Math.min(10, Math.max(1, form.top_k))
  })
  if (loading.value && activeRequestKey === requestKey) return
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  activeRequestKey = requestKey
  loading.value = true
  error.value = ''
  clarification.value = ''
  try {
    result.value = await queryAwareRetrievalApi({
      query: form.query,
      request_id: createRequestId(),
      retrieval_mode: form.retrieval_mode,
      top_k: Math.min(10, Math.max(1, form.top_k)),
      enable_llm: false,
      allow_real_api: false,
      persist_result: true
    }, controller.signal)
  } catch (err) {
    if (axios.isCancel(err)) return
    error.value = err instanceof Error ? err.message : '查询感知识库检索失败'
  } finally {
    if (activeController === controller) {
      loading.value = false
      activeController = null
      activeRequestKey = ''
    }
  }
}

async function submitClarification() {
  if (!result.value?.conversation_id || !clarification.value) return
  activeController?.abort()
  const controller = new AbortController()
  activeController = controller
  activeRequestKey = `clarify:${result.value.conversation_id}:${clarification.value}`
  loading.value = true
  error.value = ''
  try {
    result.value = await clarifyRetrievalQueryApi({
      conversation_id: result.value.conversation_id,
      clarification: clarification.value,
      enable_llm: true
    }, controller.signal)
    clarification.value = ''
  } catch (err) {
    if (axios.isCancel(err)) return
    error.value = err instanceof Error ? err.message : '补充信息提交失败'
  } finally {
    if (activeController === controller) {
      loading.value = false
      activeController = null
      activeRequestKey = ''
    }
  }
}

onUnmounted(() => {
  if (submitTimer) clearTimeout(submitTimer)
  activeController?.abort()
})

function decimal(value: unknown) { return typeof value === 'number' ? value.toFixed(3) : '-' }
function percent(value: unknown) { return typeof value === 'number' ? `${(value * 100).toFixed(1)}%` : '-' }
function shortId(value: unknown) { return typeof value === 'string' ? value.slice(0, 12) : '-' }
function createRequestId() {
  return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? `ui_${crypto.randomUUID()}`
    : `ui_${Date.now()}_${Math.random().toString(16).slice(2)}`
}
</script>
