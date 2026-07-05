<template>
  <PageFrame title="知识文档" code="KNOWLEDGE / DOCUMENTS" description="上传并管理华为与阳光电源光伏逆变器检修资料，解析结果由后端写入 PostgreSQL。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadDocuments">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="上传并解析" subtitle="支持 TXT、MD、PDF、DOCX；文件由后端保存到上传目录，不写入前端目录。">
        <form class="grid gap-3" @submit.prevent="uploadDocument">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            文件
            <input class="scada-input" type="file" accept=".txt,.md,.pdf,.docx" required @change="onFileChange" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            文档标题
            <input v-model.trim="form.title" class="scada-input" placeholder="为空时使用文件名" />
          </label>
          <div class="grid grid-cols-2 gap-3">
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
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            文档类型
            <select v-model="form.document_type" class="scada-input">
              <option v-for="item in documentTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            来源
            <input v-model.trim="form.source" class="scada-input" placeholder="如：厂家手册、现场记录" />
          </label>
          <button class="scada-button primary" type="submit" :disabled="uploading">
            <Upload :size="16" />
            {{ uploading ? '上传解析中' : '上传并解析' }}
          </button>
        </form>
      </DataPanel>

      <DataPanel title="文档列表" subtitle="点击文档可查看真实切片内容。">
        <div class="mb-4 grid gap-3 md:grid-cols-5">
          <input v-model.trim="filters.keyword" class="scada-input md:col-span-2" placeholder="搜索标题" />
          <select v-model="filters.manufacturer" class="scada-input">
            <option value="">不限厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.document_type" class="scada-input">
            <option value="">不限类型</option>
            <option v-for="item in documentTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <button class="scada-button" type="button" @click="loadDocuments">
            <Search :size="16" />
            查询
          </button>
        </div>

        <div v-if="documents.length" class="space-y-3">
          <article v-for="doc in documents" :key="doc.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 class="font-black text-white">{{ doc.title }}</h3>
                <p class="mt-1 text-xs text-slate-400">
                  {{ labelOf(doc.manufacturer) }} / {{ doc.product_series || '-' }} / {{ labelOf(doc.document_type) }}
                </p>
                <p class="mt-1 text-xs text-slate-500">
                  {{ doc.original_file_name || doc.file_name || '无文件名' }} · {{ formatSize(doc.file_size) }} · {{ formatTime(doc.created_at) }}
                </p>
              </div>
              <div class="flex flex-wrap items-center gap-2">
                <StatusPill :value="doc.parse_status" />
                <span class="rounded-full border border-cyan-300/30 bg-cyan-400/10 px-2.5 py-1 text-xs font-bold text-cyan-200">切片 {{ doc.chunk_count }}</span>
                <span class="rounded-full border border-emerald-300/30 bg-emerald-400/10 px-2.5 py-1 text-xs font-bold text-emerald-200">
                  向量索引 {{ vectorStatusByDocument[doc.id]?.indexed_count ?? 0 }}/{{ doc.chunk_count }}
                </span>
                <button class="scada-button !min-h-8 !px-3" type="button" @click="selectDocument(doc)">查看切片</button>
                <button v-if="canIndexVector" class="scada-button !min-h-8 !px-3" type="button" @click="indexDocumentVector(doc.id)">重新向量索引</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click="reparseDocument(doc.id)">重新解析</button>
                <button class="scada-button !min-h-8 !px-3" type="button" @click="removeDocument(doc.id)">归档/删除</button>
              </div>
            </div>
            <p v-if="doc.error_message" class="mt-3 rounded-md border border-red-400/20 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {{ doc.error_message }}
            </p>
          </article>
        </div>
        <EmptyState v-else text="暂无知识文档" />
      </DataPanel>
    </div>

    <DataPanel title="故障与现场图片" subtitle="图片通过 /api/media/upload 保存，可用于后续诊断与检索；当前不伪造文档与图片的独立数据库关系。">
      <label class="mb-3 grid gap-1 text-sm font-bold text-slate-200 md:max-w-xl">
        关联设备
        <select v-model="mediaDeviceId" class="scada-input">
          <option value="">不绑定设备</option>
          <option v-for="device in devices" :key="device.id" :value="device.id">
            {{ device.device_name }} / {{ device.product_series || '-' }}
          </option>
        </select>
      </label>
      <MediaEvidencePicker
        v-model="knowledgeMediaIds"
        title="上传或选择知识辅助图片"
        :device-id="mediaDeviceId"
        :manufacturer="form.manufacturer"
        :product-series="form.product_series"
      />
    </DataPanel>

    <DataPanel v-if="selectedDocument" :title="`切片预览：${selectedDocument.title}`" subtitle="内容来自后端知识切片表（knowledge_chunks）。">
      <div class="mb-3 flex items-center justify-between">
        <div class="text-xs text-slate-400">共 {{ chunkTotal }} 条切片</div>
        <button class="scada-button !min-h-8" type="button" @click="selectedDocument = null">关闭</button>
      </div>
      <div v-if="chunks.length" class="space-y-3">
        <article v-for="chunk in chunks" :key="chunk.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-wrap items-center gap-2 text-xs text-slate-400">
            <span class="font-mono text-cyan-200">#{{ chunk.chunk_index }}</span>
            <span>{{ chunk.section_title || '未标注章节' }}</span>
            <span>{{ chunk.char_count }} 字符</span>
            <span>页码 {{ chunk.page_number ?? '-' }}</span>
            <StatusPill
              :value="chunk.embedding_status"
              :label="chunk.embedding_status === 'pending' ? '向量检索未启用' : formatStatusLabel(chunk.embedding_status)"
            />
          </div>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200">{{ chunk.content }}</p>
        </article>
      </div>
      <EmptyState v-else text="该文档暂无切片" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RefreshCcw, Search, Upload } from '@lucide/vue'
import { deleteDocumentApi, getDevicesApi, getDocumentChunksApi, getDocumentVectorStatusApi, getDocumentsApi, indexDocumentVectorApi, reparseDocumentApi, uploadDocumentApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidencePicker from '@/components/MediaEvidencePicker.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useUserStore } from '@/stores/user'
import { documentTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { DeviceItem, DocumentVectorIndexStatus, KnowledgeChunk, KnowledgeDocument } from '@/types'
import { formatStatusLabel } from '@/utils/display'

const documents = ref<KnowledgeDocument[]>([])
const vectorStatusByDocument = ref<Record<string, DocumentVectorIndexStatus>>({})
const devices = ref<DeviceItem[]>([])
const chunks = ref<KnowledgeChunk[]>([])
const selectedDocument = ref<KnowledgeDocument | null>(null)
const selectedFile = ref<File | null>(null)
const mediaDeviceId = ref('')
const knowledgeMediaIds = ref<string[]>([])
const chunkTotal = ref(0)
const loading = ref(false)
const uploading = ref(false)
const error = ref('')
const userStore = useUserStore()
const filters = reactive({ keyword: '', manufacturer: '', document_type: '' })
const form = reactive({
  title: '',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  device_type: 'pv_inverter',
  document_type: 'manual',
  source: ''
})

const seriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === form.manufacturer))
const canIndexVector = computed(() => ['admin', 'expert'].includes(userStore.role || ''))

watch(
  () => form.manufacturer,
  () => {
    form.product_series = seriesOptions.value[0]?.value ?? ''
  }
)

async function loadDocuments() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50, device_type: 'pv_inverter' }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.manufacturer) params.manufacturer = filters.manufacturer
    if (filters.document_type) params.document_type = filters.document_type
    const result = await getDocumentsApi(params)
    documents.value = result.items
    await loadVectorStatuses()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '知识文档读取失败'
    documents.value = []
  } finally {
    loading.value = false
  }
}

async function loadVectorStatuses() {
  const entries = await Promise.all(
    documents.value.map(async (doc) => {
      try {
        return [doc.id, await getDocumentVectorStatusApi(doc.id)] as const
      } catch {
        return [doc.id, null] as const
      }
    })
  )
  vectorStatusByDocument.value = Object.fromEntries(entries.filter(([, value]) => Boolean(value))) as Record<string, DocumentVectorIndexStatus>
}

async function loadDevices() {
  try {
    const result = await getDevicesApi({ page: 1, page_size: 100, device_type: 'pv_inverter' })
    devices.value = result.items
  } catch {
    devices.value = []
  }
}

async function uploadDocument() {
  error.value = ''
  if (!selectedFile.value) {
    error.value = '请选择需要上传的检修资料'
    return
  }
  uploading.value = true
  try {
    const payload = new FormData()
    payload.append('file', selectedFile.value)
    payload.append('manufacturer', form.manufacturer)
    payload.append('product_series', form.product_series)
    payload.append('device_type', form.device_type)
    payload.append('document_type', form.document_type)
    if (form.title) payload.append('title', form.title)
    if (form.source) payload.append('source', form.source)
    const result = await uploadDocumentApi(payload)
    window.dispatchEvent(
      new CustomEvent('app:toast', {
        detail: { message: `解析状态：${formatStatusLabel(result.parse_status)}，生成切片：${result.chunk_count}` }
      })
    )
    form.title = ''
    form.source = ''
    selectedFile.value = null
    await loadDocuments()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '文档上传解析失败'
  } finally {
    uploading.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

async function selectDocument(doc: KnowledgeDocument) {
  selectedDocument.value = doc
  chunks.value = []
  chunkTotal.value = 0
  try {
    const result = await getDocumentChunksApi(doc.id, { page: 1, page_size: 20 })
    chunks.value = result.items
    chunkTotal.value = result.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : '切片读取失败'
  }
}

async function reparseDocument(documentId: string) {
  error.value = ''
  try {
    await reparseDocumentApi(documentId)
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: '已提交重新解析' } }))
    await loadDocuments()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '重新解析提交失败'
  }
}

async function indexDocumentVector(documentId: string) {
  error.value = ''
  try {
    const result = await indexDocumentVectorApi(documentId, {
      vector_backend: 'fake_in_memory',
      provider: 'deterministic_test',
      force: true
    })
    window.dispatchEvent(
      new CustomEvent('app:toast', {
        detail: { message: `向量索引完成：成功 ${result.succeeded}，跳过 ${result.skipped}，后端 ${result.vector_backend}` }
      })
    )
    await loadVectorStatuses()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '向量索引提交失败'
  }
}

async function removeDocument(documentId: string) {
  if (!window.confirm('确认归档或删除该知识文档？')) return
  error.value = ''
  try {
    await deleteDocumentApi(documentId)
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: '知识文档已处理' } }))
    if (selectedDocument.value?.id === documentId) {
      selectedDocument.value = null
      chunks.value = []
      chunkTotal.value = 0
    }
    await loadDocuments()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '知识文档归档或删除失败'
  }
}

function labelOf(value?: string | null) {
  const options = [...manufacturerOptions, ...documentTypeOptions]
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatSize(value?: number | null) {
  if (!value) return '-'
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

onMounted(async () => {
  await Promise.all([loadDocuments(), loadDevices()])
})
</script>
