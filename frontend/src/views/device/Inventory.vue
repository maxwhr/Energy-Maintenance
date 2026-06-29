<template>
  <PageFrame title="设备台账" code="DEVICE / INVENTORY" description="维护华为与阳光电源光伏逆变器基础台账、设备详情、退役操作和维修履历。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadAll">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 lg:grid-cols-5">
      <DataPanel v-for="card in statisticCards" :key="card.label" :title="card.label">
        <div class="text-2xl font-black text-white">{{ card.value }}</div>
      </DataPanel>
    </div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel :title="editingId ? '编辑光伏逆变器' : '新增光伏逆变器'">
        <form class="grid gap-3" @submit.prevent="saveDevice">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            设备名称
            <input v-model.trim="form.device_name" class="scada-input" required />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            设备编号
            <input v-model.trim="form.device_code" class="scada-input" />
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
          <input v-model.trim="form.model" class="scada-input" placeholder="型号，例如 SUN2000-50KTL-M3" />
          <input v-model.trim="form.station_name" class="scada-input" placeholder="电站名称" />
          <input v-model.trim="form.location" class="scada-input" placeholder="安装位置" />
          <select v-model="form.status" class="scada-input">
            <option value="normal">正常</option>
            <option value="fault">故障</option>
            <option value="maintenance">检修中</option>
            <option value="offline">离线</option>
            <option value="retired">退役</option>
          </select>
          <textarea v-model.trim="form.description" class="scada-input min-h-20" placeholder="设备说明"></textarea>
          <div class="flex flex-wrap gap-2">
            <button class="scada-button primary" type="submit" :disabled="saving">
              <Save :size="16" />
              {{ saving ? '保存中' : editingId ? '保存修改' : '保存台账' }}
            </button>
            <button v-if="editingId" class="scada-button" type="button" @click="resetForm">取消编辑</button>
          </div>
        </form>
      </DataPanel>

      <DataPanel title="逆变器列表" subtitle="支持按厂家、产品系列和设备状态过滤。">
        <div class="mb-4 grid gap-3 md:grid-cols-4">
          <select v-model="filters.manufacturer" class="scada-input">
            <option value="">不限厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.product_series" class="scada-input">
            <option value="">不限系列</option>
            <option v-for="item in productSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.status" class="scada-input">
            <option value="">不限状态</option>
            <option value="normal">正常</option>
            <option value="fault">故障</option>
            <option value="maintenance">检修中</option>
            <option value="offline">离线</option>
            <option value="retired">退役</option>
          </select>
          <button class="scada-button" type="button" @click="loadDevices">
            <Search :size="16" />
            查询
          </button>
        </div>

        <div v-if="devices.length" class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="text-xs uppercase text-slate-400">
              <tr>
                <th class="px-3 py-2">设备</th>
                <th class="px-3 py-2">厂家</th>
                <th class="px-3 py-2">系列</th>
                <th class="px-3 py-2">状态</th>
                <th class="px-3 py-2">履历</th>
                <th class="px-3 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="device in devices" :key="device.id" class="border-t border-slate-600/20 text-slate-200">
                <td class="px-3 py-3">
                  <div class="font-bold text-white">{{ device.device_name }}</div>
                  <div class="text-xs text-slate-400">{{ device.device_code || '未填写编号' }}</div>
                </td>
                <td class="px-3 py-3">{{ labelOf(device.manufacturer) }}</td>
                <td class="px-3 py-3">{{ device.product_series || '-' }}</td>
                <td class="px-3 py-3"><StatusPill :value="device.status" /></td>
                <td class="px-3 py-3">{{ device.maintenance_count }}</td>
                <td class="px-3 py-3">
                  <div class="flex flex-wrap gap-2">
                    <button class="scada-button !min-h-8 !px-3" type="button" @click="selectDevice(device.id)">详情</button>
                    <button class="scada-button !min-h-8 !px-3" type="button" @click="editDevice(device)">编辑</button>
                    <button class="scada-button !min-h-8 !px-3" type="button" @click="retireDevice(device.id)">退役</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else text="暂无设备台账数据" />
      </DataPanel>
    </div>

    <div v-if="selectedDevice" class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <DataPanel title="设备详情">
        <div class="grid gap-3 md:grid-cols-2">
          <div v-for="item in selectedDeviceDetails" :key="item.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
            <div class="text-xs font-bold text-slate-400">{{ item.label }}</div>
            <div class="mt-1 break-words text-sm font-bold text-white">{{ item.value }}</div>
          </div>
        </div>
      </DataPanel>

      <DataPanel title="新增维修履历">
        <form class="grid gap-3" @submit.prevent="createRecord">
          <select v-model="recordForm.fault_type" class="scada-input">
            <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <input v-model.trim="recordForm.alarm_code" class="scada-input" placeholder="告警代码" />
          <textarea v-model.trim="recordForm.fault_description" class="scada-input min-h-20" placeholder="故障描述"></textarea>
          <textarea v-model.trim="recordForm.repair_action" class="scada-input min-h-20" required placeholder="检修处理措施"></textarea>
          <input v-model.trim="recordForm.verification_result" class="scada-input" required placeholder="复检结果" />
          <button class="scada-button primary" type="submit">保存履历</button>
        </form>
      </DataPanel>

      <DataPanel title="维修履历" class="xl:col-span-2">
        <div v-if="maintenanceRecords.length" class="space-y-3">
          <article v-for="record in maintenanceRecords" :key="String(record.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="font-black text-white">{{ labelOf(record.fault_type as string) }} / {{ record.alarm_code || '-' }}</div>
            <p class="mt-2 text-sm leading-6 text-slate-300">{{ record.repair_action || record.fault_description || '-' }}</p>
            <p class="mt-2 text-xs text-slate-400">{{ formatTime(record.created_at as string) }}</p>
          </article>
        </div>
        <EmptyState v-else text="该设备暂无维修履历" />
      </DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { RefreshCcw, Save, Search } from '@lucide/vue'
import {
  createDeviceApi,
  createDeviceMaintenanceRecordApi,
  getDeviceApi,
  getDeviceMaintenanceRecordsApi,
  getDevicesApi,
  getDeviceStatisticsApi,
  retireDeviceApi,
  updateDeviceApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { faultTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'
import type { DeviceItem, DeviceStatistics } from '@/types'
import { formatDeviceTypeLabel, formatStatusLabel } from '@/utils/display'

const devices = ref<DeviceItem[]>([])
const selectedDevice = ref<DeviceItem | null>(null)
const maintenanceRecords = ref<Record<string, unknown>[]>([])
const statistics = ref<DeviceStatistics | null>(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const editingId = ref('')
const filters = reactive({ manufacturer: '', product_series: '', status: '' })
const form = reactive({
  device_name: '',
  device_code: '',
  manufacturer: 'huawei',
  product_series: 'SUN2000',
  model: '',
  device_type: 'pv_inverter',
  station_name: '',
  location: '',
  status: 'normal',
  description: ''
})
const recordForm = reactive({
  fault_type: 'unknown',
  alarm_code: '',
  fault_description: '',
  repair_action: '',
  verification_result: ''
})

const seriesOptions = computed(() => productSeriesOptions.filter((item) => item.manufacturer === form.manufacturer))
const selectedDeviceDetails = computed(() => {
  const device = selectedDevice.value
  if (!device) return []
  return [
    { label: '设备名称', value: device.device_name },
    { label: '设备编号', value: device.device_code || '-' },
    { label: '厂家', value: labelOf(device.manufacturer) },
    { label: '产品系列', value: device.product_series || '-' },
    { label: '型号', value: device.model || '-' },
    { label: '设备类型', value: formatDeviceTypeLabel(device.device_type || 'pv_inverter') },
    { label: '电站', value: device.station_name || '-' },
    { label: '位置', value: device.location || '-' },
    { label: '状态', value: formatStatusLabel(device.status) },
    { label: '故障次数', value: String(device.fault_count ?? 0) },
    { label: '检修次数', value: String(device.maintenance_count ?? 0) },
    { label: '更新时间', value: formatTime(device.updated_at) },
    { label: '说明', value: device.description || '-' }
  ]
})
const statisticCards = computed(() => [
  { label: '设备总数', value: statistics.value?.total_devices ?? 0 },
  { label: '正常', value: statistics.value?.normal_devices ?? 0 },
  { label: '故障', value: statistics.value?.fault_devices ?? 0 },
  { label: '检修中', value: statistics.value?.maintenance_devices ?? 0 },
  { label: '退役', value: statistics.value?.retired_devices ?? 0 }
])

watch(
  () => form.manufacturer,
  () => {
    form.product_series = seriesOptions.value[0]?.value ?? ''
  }
)

async function loadAll() {
  await Promise.all([loadStatistics(), loadDevices()])
}

async function loadStatistics() {
  try {
    statistics.value = await getDeviceStatisticsApi()
  } catch {
    statistics.value = null
  }
}

async function loadDevices() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50, device_type: 'pv_inverter' }
    if (filters.manufacturer) params.manufacturer = filters.manufacturer
    if (filters.product_series) params.product_series = filters.product_series
    if (filters.status) params.status = filters.status
    const result = await getDevicesApi(params)
    devices.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设备列表读取失败'
    devices.value = []
  } finally {
    loading.value = false
  }
}

async function saveDevice() {
  saving.value = true
  error.value = ''
  const payload = { ...form }
  try {
    if (editingId.value) {
      await updateDeviceApi(editingId.value, payload)
      toast('设备台账已更新')
    } else {
      await createDeviceApi(payload)
      toast('设备台账已保存')
    }
    resetForm()
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设备保存失败'
  } finally {
    saving.value = false
  }
}

function editDevice(device: DeviceItem) {
  editingId.value = device.id
  form.device_name = device.device_name
  form.device_code = device.device_code || ''
  form.manufacturer = device.manufacturer
  form.product_series = device.product_series || seriesOptions.value[0]?.value || 'SUN2000'
  form.model = device.model || ''
  form.station_name = device.station_name || ''
  form.location = device.location || ''
  form.status = device.status
  form.description = device.description || ''
}

async function selectDevice(id: string) {
  error.value = ''
  try {
    selectedDevice.value = await getDeviceApi(id)
    const records = await getDeviceMaintenanceRecordsApi(id, { page: 1, page_size: 20 })
    maintenanceRecords.value = records.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设备详情读取失败'
  }
}

async function retireDevice(id: string) {
  if (!window.confirm('确认退役该设备？')) return
  error.value = ''
  try {
    await retireDeviceApi(id)
    toast('设备已退役')
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设备退役失败'
  }
}

async function createRecord() {
  if (!selectedDevice.value) return
  error.value = ''
  try {
    await createDeviceMaintenanceRecordApi(selectedDevice.value.id, {
      fault_type: recordForm.fault_type,
      alarm_code: recordForm.alarm_code || undefined,
      fault_description: recordForm.fault_description || undefined,
      repair_action: recordForm.repair_action,
      verification_result: recordForm.verification_result,
      completed_at: new Date().toISOString()
    })
    toast('维修履历已保存')
    recordForm.alarm_code = ''
    recordForm.fault_description = ''
    recordForm.repair_action = ''
    recordForm.verification_result = ''
    await selectDevice(selectedDevice.value.id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '维修履历保存失败'
  }
}

function resetForm() {
  editingId.value = ''
  form.device_name = ''
  form.device_code = ''
  form.manufacturer = 'huawei'
  form.product_series = 'SUN2000'
  form.model = ''
  form.station_name = ''
  form.location = ''
  form.status = 'normal'
  form.description = ''
}

function labelOf(value?: string | null) {
  const options = [...manufacturerOptions, ...faultTypeOptions]
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(loadAll)
</script>
