<template>
  <section class="space-y-3 rounded-md border border-slate-600/20 bg-black/15 p-3">
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h3 class="text-sm font-black text-white">{{ title }}</h3>
        <p class="mt-1 text-xs leading-5 text-slate-400">
          支持 jpg、jpeg、png、webp。当前未启用 OCR/图像识别，图片仅作人工查看证据。
        </p>
      </div>
      <button class="scada-button !min-h-8 !px-3" type="button" :disabled="loading" @click="loadMedia">
        <RefreshCcw :size="14" />
        刷新
      </button>
    </div>

    <div v-if="canUpload" class="grid gap-3 md:grid-cols-[150px_minmax(0,1fr)_auto]">
      <select v-model="uploadForm.media_type" class="scada-input">
        <option value="fault_image">故障图片</option>
        <option value="site_photo">现场图片</option>
        <option value="inspection_photo">巡检/完工图片</option>
        <option value="nameplate">铭牌图片</option>
        <option value="other">其他图片</option>
      </select>
      <input
        class="scada-input"
        type="file"
        accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
        @change="onFileChange"
      />
      <button class="scada-button primary" type="button" :disabled="uploading || !selectedFile" @click="upload">
        <Upload :size="15" />
        {{ uploading ? '上传中' : '上传并关联' }}
      </button>
      <input
        v-model.trim="uploadForm.description"
        class="scada-input md:col-span-3"
        placeholder="人工描述：拍摄位置、可见告警、现场状态等"
      />
    </div>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
      {{ error }}
    </div>

    <div v-if="items.length" class="grid gap-2 sm:grid-cols-2">
      <label
        v-for="item in items"
        :key="item.id"
        class="flex cursor-pointer gap-3 rounded-md border border-slate-600/20 bg-black/20 p-3"
        :class="{ 'border-cyan-300/50 bg-cyan-400/10': isSelected(item.id) }"
      >
        <input
          type="checkbox"
          class="mt-1 h-4 w-4 accent-cyan-400"
          :checked="isSelected(item.id)"
          :disabled="readonly"
          @change="toggle(item.id)"
        />
        <span class="min-w-0">
          <span class="block truncate text-sm font-bold text-white">{{ item.original_file_name || item.file_name }}</span>
          <span class="mt-1 block text-xs text-slate-400">
            {{ formatMediaTypeLabel(item.media_type) }} / {{ item.device_name || item.product_series || '未关联设备' }} /
            文字识别 {{ formatStatusLabel(item.ocr_status || 'disabled') }}
          </span>
          <span v-if="item.ocr_text" class="mt-1 line-clamp-1 block text-xs text-cyan-100">
            已有 OCR 文本：{{ item.ocr_text.replace(/\s+/g, ' ').slice(0, 80) }}
          </span>
          <span v-if="item.description" class="mt-1 line-clamp-2 block text-xs leading-5 text-slate-300">{{ item.description }}</span>
        </span>
      </label>
    </div>
    <div v-else class="rounded-md bg-white/[0.03] px-3 py-4 text-center text-xs text-slate-500">
      当前筛选范围暂无图片资料
    </div>

    <MediaEvidenceGallery :items="selectedItems" />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RefreshCcw, Upload } from '@lucide/vue'
import { getMediaApi, uploadMediaApi } from '@/api'
import { useUserStore } from '@/stores/user'
import type { UploadedMediaItem } from '@/types'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import { formatMediaTypeLabel, formatStatusLabel } from '@/utils/display'

const props = withDefaults(
  defineProps<{
    modelValue: string[]
    title?: string
    deviceId?: string
    manufacturer?: string
    productSeries?: string
    faultType?: string
    alarmCode?: string
    taskId?: string
    readonly?: boolean
  }>(),
  {
    title: '现场图片证据',
    deviceId: '',
    manufacturer: '',
    productSeries: '',
    faultType: '',
    alarmCode: '',
    taskId: '',
    readonly: false
  }
)

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
  uploaded: [item: UploadedMediaItem]
}>()

const userStore = useUserStore()
const items = ref<UploadedMediaItem[]>([])
const selectedFile = ref<File | null>(null)
const loading = ref(false)
const uploading = ref(false)
const error = ref('')
const uploadForm = reactive({ media_type: 'fault_image', description: '' })

const canUpload = computed(() => !props.readonly && userStore.role !== 'viewer')
const selectedItems = computed(() => items.value.filter((item) => props.modelValue.includes(item.id)))

function isSelected(id: string) {
  return props.modelValue.includes(id)
}

function toggle(id: string) {
  if (props.readonly) return
  const next = isSelected(id)
    ? props.modelValue.filter((item) => item !== id)
    : [...props.modelValue, id]
  emit('update:modelValue', next.slice(0, 10))
}

async function loadMedia() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = {
      page: 1,
      page_size: 50,
      device_type: 'pv_inverter'
    }
    if (props.deviceId) params.device_id = props.deviceId
    else if (props.manufacturer) params.manufacturer = props.manufacturer
    if (props.taskId) params.task_id = props.taskId
    if (props.faultType) params.fault_type = props.faultType
    if (props.alarmCode) params.alarm_code = props.alarmCode
    const result = await getMediaApi(params)
    items.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '媒体资料读取失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function upload() {
  if (!selectedFile.value) return
  uploading.value = true
  error.value = ''
  try {
    const payload = new FormData()
    payload.append('file', selectedFile.value)
    payload.append('media_type', uploadForm.media_type)
    payload.append('device_type', 'pv_inverter')
    if (uploadForm.description) payload.append('description', uploadForm.description)
    if (props.deviceId) payload.append('device_id', props.deviceId)
    if (props.taskId) payload.append('task_id', props.taskId)
    if (props.manufacturer) payload.append('manufacturer', props.manufacturer)
    if (props.productSeries) payload.append('product_series', props.productSeries)
    if (props.faultType) payload.append('fault_type', props.faultType)
    if (props.alarmCode) payload.append('alarm_code', props.alarmCode)
    const result = await uploadMediaApi(payload)
    selectedFile.value = null
    uploadForm.description = ''
    await loadMedia()
    const uploaded = items.value.find((item) => item.id === result.media_id)
    if (uploaded) {
      emit('update:modelValue', [...new Set([...props.modelValue, uploaded.id])].slice(0, 10))
      emit('uploaded', uploaded)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '媒体上传失败'
  } finally {
    uploading.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

watch(
  () => [props.deviceId, props.manufacturer, props.productSeries, props.faultType, props.alarmCode, props.taskId],
  loadMedia
)

onMounted(loadMedia)
</script>
