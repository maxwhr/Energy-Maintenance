<template>
  <PageFrame title="检修问答" code="RETRIEVAL / QA" description="基于已审核的 PostgreSQL 知识切片进行关键词检索，返回可追溯的参考来源（references）。">
    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="提问">
        <form class="grid gap-3" @submit.prevent="submit">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            问题
            <textarea v-model.trim="form.query" class="scada-input min-h-36" placeholder="例如：SUN2000 绝缘阻抗低告警如何排查？" required></textarea>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            关联设备
            <select v-model="form.device_id" class="scada-input">
              <option value="">不绑定设备</option>
              <option v-for="device in devices" :key="device.id" :value="device.id">
                {{ device.device_name }} / {{ device.product_series || '-' }}
              </option>
            </select>
          </label>
          <div class="grid grid-cols-2 gap-3">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              厂家
              <select v-model="form.manufacturer" class="scada-input">
                <option value="">不限厂家</option>
                <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              产品系列
              <select v-model="form.product_series" class="scada-input">
                <option value="">不限系列</option>
                <option v-for="item in productSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
          </div>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            文档类型
            <select v-model="form.document_type" class="scada-input">
              <option value="">不限类型</option>
              <option v-for="item in documentTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            检索模式
            <select v-model="form.retrieval_mode" class="scada-input">
              <option value="hybrid">混合检索</option>
              <option value="keyword">关键词检索</option>
              <option value="vector">向量检索</option>
            </select>
          </label>
          <label class="flex items-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-sm font-bold text-cyan-100">
            <input v-model="form.enable_kg_enhancement" type="checkbox" />
            启用知识图谱增强
          </label>
          <button class="scada-button primary" type="submit" :disabled="loading">
            <Send :size="16" />
            {{ loading ? '检索中' : '提交检修问题' }}
          </button>
        </form>
        <p class="mt-3 rounded-md border border-emerald-300/20 bg-emerald-400/10 px-3 py-2 text-xs leading-5 text-emerald-100">
          默认仅检索已审核知识资料，确保检修依据可追溯。
        </p>
          <MediaEvidencePicker
            v-model="selectedMediaIds"
            class="mt-3"
            title="关联现场图片"
            :device-id="form.device_id"
            :manufacturer="form.manufacturer"
            :product-series="form.product_series"
          />
          <label v-if="selectedMediaIds.length" class="mt-3 flex items-center gap-2 rounded-md border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm font-bold text-amber-100">
            <input v-model="form.use_ocr_text" type="checkbox" />
            纳入 OCR 文本（机器识别，仅供参考）
          </label>
          <p v-if="selectedMediaIds.length && form.use_ocr_text" class="mt-2 text-xs leading-5 text-slate-400">
            若所选图片暂无 processed OCR 文本，将仅使用文本问题、媒体元数据和知识库。
          </p>
      </DataPanel>

      <DataPanel title="回答">
        <div v-if="messages.length" class="space-y-4">
          <article v-for="message in messages" :key="message.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="mb-2 flex items-center justify-between gap-3">
              <span class="font-black" :class="message.role === 'user' ? 'text-cyan-200' : 'text-emerald-200'">
                {{ message.role === 'user' ? '现场问题' : '检修建议' }}
              </span>
              <span class="text-xs text-slate-500">{{ message.time }}</span>
            </div>
            <p class="whitespace-pre-wrap text-sm leading-7 text-slate-200">{{ message.content }}</p>
          </article>
        </div>
        <EmptyState v-else text="输入检修问题后显示后端返回的回答。" />
      </DataPanel>
    </div>

    <div v-if="lastResult" class="grid gap-4 lg:grid-cols-3">
      <DataPanel title="建议步骤">
        <ol class="space-y-2 text-sm text-slate-300">
          <li v-for="(step, index) in lastResult.suggested_steps" :key="`${step}-${index}`" class="rounded-md bg-white/[0.03] px-3 py-2">
            {{ index + 1 }}. {{ step }}
          </li>
        </ol>
      </DataPanel>
      <DataPanel title="来源追溯">
        <div v-if="lastResult.references.length" class="space-y-2">
          <div v-for="ref in lastResult.references" :key="`${ref.document_id}-${ref.chunk_index}`" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
            <div class="font-bold text-white">{{ ref.document_title || ref.document_id }}</div>
            <div class="mt-1 text-xs text-slate-400">
              {{ labelOf(ref.manufacturer) }} / {{ ref.product_series || '-' }} / 切片 {{ ref.chunk_index }} / 相关度 {{ formatScore(ref.score) }}
            </div>
          </div>
        </div>
        <EmptyState v-else text="当前知识库未检索到足够相关资料，请补充光伏逆变器手册、故障案例或巡检规范。" />
      </DataPanel>
      <DataPanel title="图谱增强">
        <div v-if="hasKgContext" class="space-y-3">
          <section>
            <h3 class="mb-2 text-sm font-black text-white">命中节点</h3>
            <div class="flex flex-wrap gap-2">
              <span v-for="node in lastResult.kg_context?.matched_nodes" :key="node.id" class="rounded border border-cyan-300/20 bg-cyan-400/10 px-2 py-1 text-xs text-cyan-100">
                {{ node.display_name }}
              </span>
            </div>
          </section>
          <section>
            <h3 class="mb-2 text-sm font-black text-white">关联原因 / 措施 / 安全风险</h3>
            <ul class="space-y-2 text-sm text-slate-300">
              <li v-for="item in kgMixedItems" :key="`${item.group}-${item.id}`" class="rounded-md bg-white/[0.03] px-3 py-2">
                <span class="text-cyan-200">{{ item.group }}：</span>{{ item.name }}
              </li>
            </ul>
          </section>
          <section>
            <h3 class="mb-2 text-sm font-black text-white">图谱路径</h3>
            <p v-for="path in lastResult.kg_paths?.slice(0, 3)" :key="path.summary" class="text-xs leading-6 text-slate-400">
              {{ path.summary || '已关联图谱路径' }}
            </p>
          </section>
        </div>
        <EmptyState v-else text="未命中图谱增强，已使用知识库检索。" />
      </DataPanel>
    </div>

    <DataPanel v-if="lastResult" title="检索元数据">
      <div class="grid gap-3 text-sm text-slate-300 md:grid-cols-4">
        <div class="rounded-md bg-white/[0.03] p-3">trace_id：{{ lastResult.trace_id }}</div>
        <div class="rounded-md bg-white/[0.03] p-3">置信度（confidence）：{{ Math.round(lastResult.confidence * 100) }}%</div>
        <div class="rounded-md bg-white/[0.03] p-3">参考来源（references）：{{ lastResult.references.length }}</div>
        <div class="rounded-md bg-white/[0.03] p-3">检索片段（chunks）：{{ lastResult.retrieved_chunks.length }}</div>
        <div class="rounded-md bg-white/[0.03] p-3">检索模式：{{ retrievalModeLabel(lastResult.retrieval_mode) }}</div>
        <div class="rounded-md bg-white/[0.03] p-3">vector_backend：{{ lastResult.vector_backend || 'unavailable' }}</div>
        <div class="rounded-md bg-white/[0.03] p-3">向量可用：{{ lastResult.vector_available ? '是' : '否' }}</div>
        <div class="rounded-md bg-white/[0.03] p-3">fallback：{{ lastResult.vector_fallback_used ? '已回退关键词' : '无' }}</div>
      </div>
      <div v-if="lastResult.vector_fallback_used" class="mt-3 rounded-md border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
        向量检索不可用，已回退关键词检索。
      </div>
      <div v-if="lastResult.media_notice" class="mt-3 rounded-md border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
        {{ lastResult.media_notice }}
      </div>
      <div v-if="lastResult.ocr_context?.length" class="mt-3 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
        <div class="mb-2 text-xs font-bold text-cyan-100">OCR 上下文（机器识别，仅供参考）</div>
        <article v-for="item in lastResult.ocr_context" :key="item.media_id" class="mb-2 rounded bg-black/20 px-3 py-2 text-xs leading-5 text-slate-200">
          <div class="font-bold text-white">{{ item.file_name || item.media_id }}</div>
          <p class="mt-1 whitespace-pre-wrap">{{ item.text }}</p>
        </article>
      </div>
      <MediaEvidenceGallery v-if="lastResult.media_items?.length" class="mt-4" :items="lastResult.media_items" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Send } from '@lucide/vue'
import { getDevicesApi, streamRetrievalApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import MediaEvidencePicker from '@/components/MediaEvidencePicker.vue'
import PageFrame from '@/components/PageFrame.vue'
import { documentTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { DeviceItem, RetrievalResponse } from '@/types'

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

const messages = ref<ChatMessage[]>([])
const devices = ref<DeviceItem[]>([])
const selectedMediaIds = ref<string[]>([])
const lastResult = ref<RetrievalResponse | null>(null)
const loading = ref(false)
const error = ref('')
const form = reactive({
  query: '',
  device_id: '',
  manufacturer: '',
  product_series: '',
  document_type: '',
  top_k: 5,
  retrieval_mode: 'hybrid',
  enable_kg_enhancement: true,
  use_ocr_text: false
})
const hasKgContext = computed(() => Boolean((lastResult.value?.kg_context?.summary?.matched_node_count as number | undefined) || lastResult.value?.kg_evidence?.length))
const kgMixedItems = computed(() => {
  const context = lastResult.value?.kg_context
  if (!context) return []
  return [
    ...(context.related_causes || []).map((item) => ({ group: '可能原因', id: item.id, name: item.display_name })),
    ...(context.recommended_actions || []).map((item) => ({ group: '处理措施', id: item.id, name: item.display_name })),
    ...(context.safety_risks || []).map((item) => ({ group: '安全风险', id: item.id, name: item.display_name }))
  ].slice(0, 9)
})

async function submit() {
  loading.value = true
  error.value = ''
  const question = form.query
  messages.value.push({ id: crypto.randomUUID(), role: 'user', content: question, time: now() })
  const assistantMessageId = crypto.randomUUID()
  messages.value.push({ id: assistantMessageId, role: 'assistant', content: '', time: now() })
  try {
    const payload: Record<string, unknown> = {
      query: question,
      device_type: 'pv_inverter',
      top_k: form.top_k,
      retrieval_mode: form.retrieval_mode,
      enable_vector: form.retrieval_mode !== 'keyword'
    }
    if (form.device_id) payload.device_id = form.device_id
    if (form.manufacturer) payload.manufacturer = form.manufacturer
    if (form.product_series) payload.product_series = form.product_series
    if (form.document_type) payload.document_type = form.document_type
    if (selectedMediaIds.value.length) payload.media_ids = selectedMediaIds.value
    payload.use_ocr_text = Boolean(selectedMediaIds.value.length && form.use_ocr_text)
    payload.enable_kg_enhancement = form.enable_kg_enhancement
    payload.enable_model_enhancement = true
    payload.model_provider = 'cloud_openai'
    payload.allow_model_fallback = false
    await streamRetrievalApi(payload, (event) => {
      if (event.type === 'retrieval' && event.response) {
        lastResult.value = event.response
      }
      if (event.type === 'delta' && event.content) {
        appendAssistantContent(assistantMessageId, event.content)
      }
      if (event.type === 'done' && event.response) {
        lastResult.value = event.response
        replaceAssistantContent(assistantMessageId, event.response.answer)
      }
      if (event.type === 'error') {
        throw new Error(event.message || 'Model stream failed')
      }
    })
    form.query = ''
  } catch (err) {
    messages.value = messages.value.filter((message) => message.id !== assistantMessageId || Boolean(message.content))
    error.value = err instanceof Error ? err.message : '检修问答请求失败'
  } finally {
    loading.value = false
  }
}

async function loadDevices() {
  try {
    const data = await getDevicesApi({ page: 1, page_size: 100, device_type: 'pv_inverter' })
    devices.value = data.items
  } catch {
    devices.value = []
  }
}

function appendAssistantContent(messageId: string, content: string) {
  const message = messages.value.find((item) => item.id === messageId)
  if (message) message.content += content
}

function replaceAssistantContent(messageId: string, content?: string) {
  const message = messages.value.find((item) => item.id === messageId)
  if (message && content) message.content = content
}

watch(
  () => form.device_id,
  (deviceId) => {
    const device = devices.value.find((item) => item.id === deviceId)
    if (!device) return
    form.manufacturer = device.manufacturer
    form.product_series = device.product_series || ''
  }
)

function labelOf(value?: string | null) {
  const map: Record<string, string> = { huawei: '华为', sungrow: '阳光电源' }
  return value ? map[value] ?? value : '-'
}

function formatScore(value?: number) {
  return typeof value === 'number' ? value.toFixed(2) : '-'
}

function retrievalModeLabel(value?: string) {
  return ({ keyword: '关键词', vector: '向量', hybrid: '混合' } as Record<string, string>)[value || ''] ?? value ?? '-'
}

function now() {
  return new Date().toLocaleTimeString('zh-CN')
}

onMounted(loadDevices)
</script>
