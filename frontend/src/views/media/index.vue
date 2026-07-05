<template>
  <PageFrame title="媒体资料" code="MEDIA / LIBRARY" description="管理 JPG、JPEG、PNG、WEBP 现场图片，供诊断、检索、任务和记录追溯使用。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadMedia">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="上传现场附件" subtitle="文件直接上传至后端媒体接口，不保存到前端目录。">
        <form class="grid gap-3" @submit.prevent="upload">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            文件
            <input class="scada-input" type="file" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp" required @change="onFileChange" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            媒体类型
            <select v-model="form.media_type" class="scada-input">
              <option value="fault_image">故障图片</option>
              <option value="site_photo">现场图片</option>
              <option value="inspection_photo">巡检照片</option>
              <option value="nameplate">铭牌图片</option>
              <option value="other">其他图片</option>
            </select>
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
              故障类型
              <select v-model="form.fault_type" class="scada-input">
                <option value="">未指定</option>
                <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
              </select>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              告警代码
              <input v-model.trim="form.alarm_code" class="scada-input" placeholder="可选" />
            </label>
          </div>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            人工描述
            <textarea v-model.trim="form.description" class="scada-input min-h-20" placeholder="拍摄位置、可见告警、现场状态等"></textarea>
          </label>
          <button class="scada-button primary" type="submit" :disabled="uploading">
            <Upload :size="16" />
            {{ uploading ? '上传中' : '上传媒体' }}
          </button>
        </form>
      </DataPanel>

      <DataPanel title="媒体列表" subtitle="点击详情可查看后端返回的媒体元数据。">
        <div class="mb-4 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <select v-model="filters.media_type" class="scada-input">
            <option value="">全部类型</option>
            <option value="fault_image">故障图片</option>
            <option value="site_photo">现场图片</option>
            <option value="inspection_photo">巡检照片</option>
            <option value="nameplate">铭牌图片</option>
            <option value="other">其他图片</option>
          </select>
          <select v-model="filters.device_id" class="scada-input">
            <option value="">全部设备</option>
            <option v-for="device in devices" :key="device.id" :value="device.id">{{ device.device_name }}</option>
          </select>
          <select v-model="filters.fault_type" class="scada-input">
            <option value="">全部故障</option>
            <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.manufacturer" class="scada-input">
            <option value="">全部厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索文件名" />
          <button class="scada-button" type="button" @click="loadMedia">
            <Search :size="16" />
            查询
          </button>
        </div>

        <div v-if="mediaItems.length" class="space-y-3">
          <article v-for="item in mediaItems" :key="String(item.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 class="font-black text-white">{{ item.original_file_name || item.file_name || item.id }}</h3>
                <p class="mt-1 text-xs text-slate-400">
                  {{ formatMediaTypeLabel(item.media_type) }} / {{ labelOf(item.manufacturer as string) }} / {{ item.product_series || '-' }}
                </p>
                <p class="mt-1 text-xs text-slate-500">{{ formatSize(Number(item.file_size || 0)) }} / {{ formatTime(item.created_at as string) }}</p>
              </div>
              <button class="scada-button !min-h-8 !px-3" type="button" @click="showDetail(String(item.id))">查看详情</button>
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无媒体资料" />
      </DataPanel>
    </div>

    <DataPanel v-if="detail" title="媒体详情">
      <div class="grid gap-3 md:grid-cols-2">
        <div v-for="item in detailRows" :key="item.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
          <div class="text-xs font-bold text-slate-400">{{ item.label }}</div>
          <div class="mt-1 break-words text-sm font-bold text-white">{{ item.value }}</div>
        </div>
      </div>
      <div class="mt-4 rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <div class="text-xs font-bold text-cyan-100">OCR 文字识别</div>
            <p class="mt-1 text-xs leading-5 text-cyan-50">
              当前状态：{{ formatStatusLabel(detail.ocr_status || ocrStatus?.status || 'disabled') }} /
              {{ detail.ocr_message || ocrStatus?.message || 'OCR 未启用' }}
            </p>
          </div>
          <button v-if="canRunOcr" class="scada-button !min-h-8 !px-3" type="button" :disabled="ocrRunning || !detail" @click="runOcr(String(detail.id))">
            <ScanText :size="15" />
            {{ ocrRunning ? '识别中' : '执行 OCR' }}
          </button>
        </div>
        <p v-if="detail.ocr_error_summary" class="mt-2 text-xs leading-5 text-amber-100">{{ detail.ocr_error_summary }}</p>
        <p class="mt-2 text-xs leading-5 text-slate-300">OCR 结果为机器识别，仅供检修人员参考，不等同于图像故障识别。</p>
      </div>
      <div v-if="detail.ocr_text" class="mt-4 rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-400">OCR 文本摘录</div>
        <p class="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-200">{{ detail.ocr_text }}</p>
      </div>
      <div class="mt-4 rounded-md border border-violet-300/20 bg-violet-400/10 p-3">
        <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div class="text-xs font-bold text-violet-100">多模态证据摘要</div>
            <p class="mt-1 text-xs leading-5 text-slate-200">
              jobs={{ multimodalSummary?.jobs.length ?? 0 }} /
              OCR={{ multimodalSummary?.ocr_results.length ?? 0 }} /
              AI={{ multimodalSummary?.analyses.length ?? 0 }} /
              evidence={{ multimodalSummary?.evidence_links.length ?? 0 }}
            </p>
            <p class="mt-1 text-xs text-amber-100">机器识别仅作为辅助证据，mock-run 会明确标记为模拟结果。</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="scada-button !min-h-8 !px-3" type="button" :disabled="multimodalBusy || !canRunOcr" @click="createMultimodalJob('ocr', false)">
              OCR dry-run
            </button>
            <button class="scada-button !min-h-8 !px-3" type="button" :disabled="multimodalBusy || !canRunOcr" @click="createMultimodalJob('multimodal_analysis', false)">
              AI dry-run
            </button>
            <button class="scada-button primary !min-h-8 !px-3" type="button" :disabled="multimodalBusy || !canMockRun" @click="createMultimodalJob('multimodal_analysis', true)">
              AI mock-run
            </button>
            <RouterLink class="scada-button !min-h-8 !px-3" :to="`/multimodal?media_id=${detail.id}`">查看完整证据</RouterLink>
          </div>
        </div>
      </div>
      <MediaEvidenceGallery :items="[detail]" class="mt-4" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RefreshCcw, ScanText, Search, Upload } from '@lucide/vue'
import { createMediaProcessingJob, getDevicesApi, getMediaApi, getMediaDetailApi, getMediaMultimodalSummary, getOCRStatusApi, runMediaOCRApi, uploadMediaApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import PageFrame from '@/components/PageFrame.vue'
import { useUserStore } from '@/stores/user'
import { faultTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { DeviceItem, OCRStatusResult, UploadedMediaItem } from '@/types'
import type { MediaMultimodalSummary } from '@/types/multimodal'
import { formatDeviceTypeLabel, formatFaultTypeLabel, formatMediaTypeLabel, formatStatusLabel } from '@/utils/display'

const mediaItems = ref<UploadedMediaItem[]>([])
const detail = ref<UploadedMediaItem | null>(null)
const devices = ref<DeviceItem[]>([])
const ocrStatus = ref<OCRStatusResult | null>(null)
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const uploading = ref(false)
const ocrRunning = ref(false)
const multimodalBusy = ref(false)
const error = ref('')
const userStore = useUserStore()
const multimodalSummary = ref<MediaMultimodalSummary | null>(null)
const filters = reactive({ media_type: '', manufacturer: '', device_id: '', fault_type: '', keyword: '' })
const form = reactive({
  media_type: 'fault_image',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  device_type: 'pv_inverter',
  device_id: '',
  fault_type: '',
  alarm_code: '',
  description: ''
})

const seriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === form.manufacturer))
const canRunOcr = computed(() => userStore.role !== 'viewer')
const canMockRun = computed(() => ['admin', 'expert'].includes(userStore.role || ''))
const detailRows = computed(() => {
  if (!detail.value) return []
  return [
    { label: '文件名', value: String(detail.value.original_file_name || detail.value.file_name || '-') },
    { label: '媒体类型', value: formatMediaTypeLabel(detail.value.media_type) },
    { label: '厂家', value: labelOf(detail.value.manufacturer as string) },
    { label: '产品系列', value: String(detail.value.product_series || '-') },
    { label: '设备类型', value: formatDeviceTypeLabel(detail.value.device_type) },
    { label: '文件大小', value: formatSize(Number(detail.value.file_size || 0)) },
    { label: '扩展名', value: String(detail.value.file_ext || '-') },
    { label: '状态', value: formatStatusLabel(detail.value.status) },
    { label: '文字识别状态', value: formatStatusLabel(detail.value.ocr_status || 'disabled') },
    { label: 'OCR 引擎', value: String(detail.value.ocr_provider || '-') },
    { label: 'OCR 语言', value: String(detail.value.ocr_lang || '-') },
    { label: 'OCR 时间', value: formatTime(detail.value.ocr_processed_at as string) },
    { label: '上传人', value: String(detail.value.uploaded_by_name || '-') },
    { label: '关联设备', value: String(detail.value.device_name || detail.value.device_id || '-') },
    { label: '故障类型', value: formatFaultTypeLabel(detail.value.fault_type) },
    { label: '告警代码', value: String(detail.value.alarm_code || '-') },
    { label: '关联任务', value: String(detail.value.task_id || '-') },
    { label: '问答 trace_id', value: String(detail.value.qa_trace_id || '-') },
    { label: '上传时间', value: formatTime(detail.value.created_at as string) }
  ]
})

watch(
  () => form.manufacturer,
  () => {
    form.product_series = seriesOptions.value[0]?.value ?? ''
  }
)

async function loadMedia() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50, device_type: 'pv_inverter' }
    if (filters.media_type) params.media_type = filters.media_type
    if (filters.manufacturer) params.manufacturer = filters.manufacturer
    if (filters.device_id) params.device_id = filters.device_id
    if (filters.fault_type) params.fault_type = filters.fault_type
    if (filters.keyword) params.keyword = filters.keyword
    const result = await getMediaApi(params)
    mediaItems.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '媒体列表读取失败'
    mediaItems.value = []
  } finally {
    loading.value = false
  }
}

async function upload() {
  if (!selectedFile.value) {
    error.value = '请选择需要上传的媒体文件'
    return
  }
  uploading.value = true
  error.value = ''
  try {
    const payload = new FormData()
    payload.append('file', selectedFile.value)
    payload.append('media_type', form.media_type)
    payload.append('manufacturer', form.manufacturer)
    payload.append('product_series', form.product_series)
    payload.append('device_type', form.device_type)
    if (form.device_id) payload.append('device_id', form.device_id)
    if (form.fault_type) payload.append('fault_type', form.fault_type)
    if (form.alarm_code) payload.append('alarm_code', form.alarm_code)
    if (form.description) payload.append('description', form.description)
    await uploadMediaApi(payload)
    selectedFile.value = null
    toast('媒体资料已上传')
    await loadMedia()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '媒体上传失败'
  } finally {
    uploading.value = false
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

async function showDetail(id: string) {
  error.value = ''
  try {
    detail.value = await getMediaDetailApi(id)
    await loadMultimodalSummary(id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '媒体详情读取失败'
  }
}

async function loadMultimodalSummary(id: string) {
  try {
    multimodalSummary.value = await getMediaMultimodalSummary(id)
  } catch {
    multimodalSummary.value = null
  }
}

async function loadOcrStatus() {
  try {
    ocrStatus.value = await getOCRStatusApi()
  } catch {
    ocrStatus.value = null
  }
}

async function runOcr(id: string) {
  if (!canRunOcr.value) return
  ocrRunning.value = true
  error.value = ''
  try {
    await runMediaOCRApi(id)
    detail.value = await getMediaDetailApi(id)
    await loadMedia()
    toast('OCR 处理状态已更新')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'OCR 处理失败'
  } finally {
    ocrRunning.value = false
  }
}

async function createMultimodalJob(jobType: 'ocr' | 'multimodal_analysis', mockRun: boolean) {
  if (!detail.value) return
  if (mockRun && !canMockRun.value) {
    error.value = '当前账号没有 mock-run 权限'
    return
  }
  multimodalBusy.value = true
  error.value = ''
  try {
    await createMediaProcessingJob(String(detail.value.id), {
      job_type: jobType,
      provider_code: jobType === 'ocr' ? 'tesseract_ocr' : 'mimo_2_5',
      capability: jobType === 'ocr' ? 'ocr' : 'fault_scene_analysis',
      analysis_type: jobType === 'ocr' ? undefined : 'fault_scene',
      dry_run: !mockRun,
      mock_run: mockRun,
      input_summary: { source: 'media_page', media_id: detail.value.id }
    })
    await loadMultimodalSummary(String(detail.value.id))
    toast(mockRun ? '多模态 mock-run 已完成，结果已标记为模拟证据' : '多模态 dry-run 任务已创建')
  } catch (err) {
    error.value = err instanceof Error ? err.message : '多模态处理任务创建失败'
  } finally {
    multimodalBusy.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

function labelOf(value?: string | null) {
  return manufacturerOptions.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatSize(value?: number | null) {
  if (!value) return '-'
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(async () => {
  await loadOcrStatus()
  await loadDevices()
  await loadMedia()
})
</script>
