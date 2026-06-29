<template>
  <div v-if="items.length" class="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
    <article
      v-for="item in items"
      :key="item.id"
      class="overflow-hidden rounded-md border border-slate-600/20 bg-black/20"
    >
      <div class="aspect-[4/3] bg-slate-950/50">
        <img
          v-if="previewUrls[item.id]"
          :src="previewUrls[item.id]"
          :alt="item.original_file_name || item.file_name"
          class="h-full w-full object-contain"
        />
        <div v-else class="grid h-full place-items-center px-4 text-center text-xs text-slate-500">
          {{ previewErrors[item.id] || '图片加载中' }}
        </div>
      </div>
      <div class="space-y-1 p-3 text-xs text-slate-400">
        <div class="truncate font-bold text-white">{{ item.original_file_name || item.file_name }}</div>
        <div>{{ mediaTypeLabel(item.media_type) }} / {{ item.device_name || item.product_series || '未关联设备' }}</div>
        <div v-if="item.fault_type || item.alarm_code">{{ formatFaultTypeLabel(item.fault_type) }} / {{ item.alarm_code || '-' }}</div>
        <div>文字识别：{{ formatStatusLabel(item.ocr_status || 'disabled') }}</div>
        <p v-if="ocrPreview(item)" class="line-clamp-2 leading-5 text-cyan-100">
          OCR 摘要：{{ ocrPreview(item) }}
        </p>
        <p v-if="item.description" class="line-clamp-2 leading-5 text-slate-300">{{ item.description }}</p>
      </div>
    </article>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, reactive, watch } from 'vue'
import { getMediaContentApi } from '@/api'
import type { MediaContextItem, UploadedMediaItem } from '@/types'
import { formatFaultTypeLabel, formatMediaTypeLabel, formatStatusLabel } from '@/utils/display'

const props = defineProps<{
  items: Array<MediaContextItem | UploadedMediaItem>
}>()

const previewUrls = reactive<Record<string, string>>({})
const previewErrors = reactive<Record<string, string>>({})

async function loadPreview(id: string) {
  if (previewUrls[id] || previewErrors[id]) return
  try {
    const blob = await getMediaContentApi(id)
    previewUrls[id] = URL.createObjectURL(blob)
  } catch {
    previewErrors[id] = '图片预览加载失败'
  }
}

function clearUnused(activeIds: Set<string>) {
  Object.entries(previewUrls).forEach(([id, url]) => {
    if (!activeIds.has(id)) {
      URL.revokeObjectURL(url)
      delete previewUrls[id]
      delete previewErrors[id]
    }
  })
}

watch(
  () => props.items.map((item) => item.id),
  (ids) => {
    const activeIds = new Set(ids)
    clearUnused(activeIds)
    ids.forEach(loadPreview)
  },
  { immediate: true }
)

onBeforeUnmount(() => {
  Object.values(previewUrls).forEach((url) => URL.revokeObjectURL(url))
})

const mediaTypeLabel = formatMediaTypeLabel

function ocrPreview(item: MediaContextItem | UploadedMediaItem) {
  const text = item.ocr_text?.trim()
  return text ? text.replace(/\s+/g, ' ').slice(0, 120) : ''
}
</script>
