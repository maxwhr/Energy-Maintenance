<template>
  <PageFrame title="故障诊断" code="DIAGNOSIS / ANALYZE" description="提交光伏逆变器故障现象、告警代码与可选现场附件，后端保存诊断记录。">
    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[430px_minmax(0,1fr)]">
      <DataPanel title="诊断输入">
        <form class="grid gap-3" @submit.prevent="submit">
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
            故障类型
            <select v-model="form.fault_type" class="scada-input">
              <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            告警代码
            <input v-model.trim="form.alarm_code" class="scada-input" placeholder="如：厂商告警码或现场记录编号" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            故障现象
            <textarea v-model.trim="form.fault_description" class="scada-input min-h-32" required placeholder="描述告警、设备状态、并网状态、环境温度等现场现象。"></textarea>
          </label>
          <MediaEvidencePicker
            v-model="selectedMediaIds"
            title="现场故障图片"
            :device-id="form.device_id"
            :manufacturer="form.manufacturer"
            :product-series="form.product_series"
            :fault-type="form.fault_type"
            :alarm-code="form.alarm_code"
          />
          <label v-if="selectedMediaIds.length" class="flex items-center gap-2 rounded-md border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm font-bold text-amber-100">
            <input v-model="form.use_ocr_text" type="checkbox" />
            纳入 OCR 文本（机器识别，仅供参考）
          </label>
          <p v-if="selectedMediaIds.length && form.use_ocr_text" class="text-xs leading-5 text-slate-400">
            若所选图片暂无 processed OCR 文本，诊断将继续以人工故障描述、媒体元数据、知识库和图谱为主。
          </p>
          <label class="flex items-center gap-2 rounded-md border border-cyan-300/20 bg-cyan-400/10 px-3 py-2 text-sm font-bold text-cyan-100">
            <input v-model="form.enable_kg_enhancement" type="checkbox" />
            启用知识图谱增强
          </label>
          <button class="scada-button primary" type="submit" :disabled="loading">
            <Stethoscope :size="16" />
            {{ loading ? '诊断中' : '提交诊断' }}
          </button>
        </form>
      </DataPanel>

      <DataPanel title="诊断结果">
        <div v-if="result" class="space-y-4">
          <div class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <div class="mb-2 flex flex-wrap gap-2 text-xs text-cyan-200">
              <span>trace_id：{{ result.trace_id }}</span>
              <span>置信度（confidence）：{{ Math.round(result.confidence * 100) }}%</span>
            </div>
            <p class="whitespace-pre-wrap text-sm leading-7 text-slate-100">{{ result.diagnosis_summary }}</p>
          </div>

          <ResultList title="可能原因" :items="result.possible_causes" />
          <ResultList title="排查步骤" :items="result.inspection_steps" />
          <ResultList title="安全注意事项" :items="result.safety_notes" />
          <ResultList title="推荐处理措施" :items="result.recommended_actions" />
          <section class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-4">
            <h3 class="mb-3 text-sm font-black text-white">图谱增强建议</h3>
            <div v-if="hasKgContext" class="grid gap-3 md:grid-cols-2">
              <KgNodeList title="图谱关联原因" :items="result.kg_related_causes || []" />
              <KgNodeList title="图谱检查项" :items="result.kg_inspection_items || []" />
              <KgNodeList title="图谱推荐措施" :items="result.kg_recommended_actions || []" />
              <KgNodeList title="图谱安全风险" :items="result.kg_safety_risks || []" />
            </div>
            <EmptyState v-else text="未命中图谱增强，已使用规则诊断和知识库 references。" />
            <div v-if="result.kg_evidence?.length" class="mt-3 space-y-2">
              <article v-for="item in result.kg_evidence.slice(0, 4)" :key="item.id" class="rounded-md bg-black/20 px-3 py-2 text-xs leading-5 text-slate-300">
                {{ item.evidence_text || item.source_type }}
              </article>
            </div>
          </section>
          <div v-if="result.media_notice" class="rounded-md border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm leading-6 text-amber-100">
            {{ result.media_notice }}
          </div>
          <div v-if="result.ocr_context?.length" class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
            <div class="mb-2 text-xs font-bold text-cyan-100">OCR 上下文（机器识别，仅供参考）</div>
            <article v-for="item in result.ocr_context" :key="item.media_id" class="mb-2 rounded bg-black/20 px-3 py-2 text-xs leading-5 text-slate-200">
              <div class="font-bold text-white">{{ item.file_name || item.media_id }}</div>
              <p class="mt-1 whitespace-pre-wrap">{{ item.text }}</p>
            </article>
          </div>
          <MediaEvidenceGallery v-if="result.media_items?.length" :items="result.media_items" />
        </div>
        <EmptyState v-else text="提交故障现象后显示后端诊断结果。" />
      </DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref, watch, type PropType } from 'vue'
import { useRoute } from 'vue-router'
import { Stethoscope } from '@lucide/vue'
import { analyzeDiagnosisApi, getDevicesApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import MediaEvidencePicker from '@/components/MediaEvidencePicker.vue'
import PageFrame from '@/components/PageFrame.vue'
import { faultTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { DeviceItem, DiagnosisResponse } from '@/types'

const ResultList = defineComponent({
  props: {
    title: { type: String, required: true },
    items: { type: Array as PropType<string[]>, required: true }
  },
  setup(props) {
    return () =>
      h('section', [
        h('h3', { class: 'mb-2 text-sm font-black text-white' }, props.title),
        props.items.length
          ? h(
              'ol',
              { class: 'space-y-2 text-sm text-slate-300' },
              props.items.map((item, index) =>
                h('li', { class: 'rounded-md bg-white/[0.03] px-3 py-2', key: `${item}-${index}` }, `${index + 1}. ${item}`)
              )
            )
          : h('div', { class: 'rounded-md bg-white/[0.03] px-3 py-2 text-sm text-slate-400' }, '暂无')
      ])
  }
})

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

const devices = ref<DeviceItem[]>([])
const route = useRoute()
const result = ref<DiagnosisResponse | null>(null)
const selectedMediaIds = ref<string[]>([])
const loading = ref(false)
const error = ref('')
const form = reactive({
  device_id: '',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  device_type: 'pv_inverter',
  fault_type: String(route.query.fault_type || faultTypeOptions[0]?.value || 'alarm_code_query'),
  alarm_code: String(route.query.alarm_code || ''),
  fault_description: '',
  enable_kg_enhancement: true,
  use_ocr_text: false
})

if (route.query.manufacturer && manufacturerOptions.some((item) => item.value === route.query.manufacturer)) {
  form.manufacturer = String(route.query.manufacturer)
}
if (route.query.product_series && productSeriesOptions.some((item) => item.value === route.query.product_series)) {
  form.product_series = String(route.query.product_series)
}
const hasKgContext = computed(() => Boolean((result.value?.kg_context?.summary?.matched_node_count as number | undefined) || result.value?.kg_evidence?.length))

const seriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === form.manufacturer))

watch(
  () => form.manufacturer,
  () => {
    if (!seriesOptions.value.some((item) => item.value === form.product_series)) {
      form.product_series = seriesOptions.value[0]?.value ?? ''
    }
  }
)

watch(
  () => form.device_id,
  (deviceId) => {
    const device = devices.value.find((item) => item.id === deviceId)
    if (!device) return
    form.manufacturer = device.manufacturer
    form.product_series = device.product_series || ''
  }
)

async function loadDevices() {
  try {
    const data = await getDevicesApi({ page: 1, page_size: 100, device_type: 'pv_inverter' })
    devices.value = data.items
  } catch {
    devices.value = []
  }
}

async function submit() {
  loading.value = true
  error.value = ''
  result.value = null
  try {
    const payload: Record<string, unknown> = {
      manufacturer: form.manufacturer,
      product_series: form.product_series,
      device_type: 'pv_inverter',
      fault_type: form.fault_type,
      alarm_code: form.alarm_code || undefined,
      fault_description: form.fault_description,
      media_ids: selectedMediaIds.value,
      use_ocr_text: Boolean(selectedMediaIds.value.length && form.use_ocr_text),
      enable_kg_enhancement: form.enable_kg_enhancement
    }
    if (form.device_id) payload.device_id = form.device_id
    result.value = await analyzeDiagnosisApi(payload)
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: '诊断记录已保存' } }))
  } catch (err) {
    error.value = err instanceof Error ? err.message : '故障诊断失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadDevices)
</script>
