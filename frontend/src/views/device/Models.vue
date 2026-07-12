<template>
  <PageFrame title="产品系列与型号" code="DEVICE / SERIES" description="基于现有设备台账汇总华为 SUN2000、FusionSolar 与阳光电源 SG 系列，不创建或伪造型号数据。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadDevices">
        <RefreshCcw :size="16" />
        {{ loading ? '刷新中' : '刷新台账' }}
      </button>
      <RouterLink class="scada-button primary" to="/device/inventory">
        <ListTree :size="16" />
        查看设备台账
      </RouterLink>
    </template>

    <PageNotice v-if="error" tone="error" title="台账读取失败" :message="error" retry @retry="loadDevices" />
    <PageNotice v-else-if="loading" tone="loading" message="正在读取设备台账并汇总产品系列…" />

    <div class="grid gap-4 lg:grid-cols-3">
      <DataPanel v-for="series in seriesCards" :key="series.value" :title="series.label" :subtitle="series.manufacturerLabel">
        <div class="space-y-4">
          <div class="grid grid-cols-3 gap-2">
            <div class="rounded-lg border border-slate-600/20 bg-black/20 p-3">
              <div class="text-[11px] font-bold text-slate-400">台账设备</div>
              <div class="mt-1 text-2xl font-black text-white">{{ series.count }}</div>
            </div>
            <div class="rounded-lg border border-slate-600/20 bg-black/20 p-3">
              <div class="text-[11px] font-bold text-slate-400">在运设备</div>
              <div class="mt-1 text-2xl font-black text-emerald-200">{{ series.activeCount }}</div>
            </div>
            <div class="rounded-lg border border-slate-600/20 bg-black/20 p-3">
              <div class="text-[11px] font-bold text-slate-400">已录型号</div>
              <div class="mt-1 text-2xl font-black text-cyan-200">{{ series.models.length }}</div>
            </div>
          </div>
          <p class="text-sm leading-6 text-slate-300">{{ series.description }}</p>
          <div class="flex flex-wrap gap-2">
            <span v-for="model in series.models.slice(0, 6)" :key="model" class="rounded-full border border-cyan-300/20 bg-cyan-400/10 px-2.5 py-1 text-xs font-bold text-cyan-200">{{ model }}</span>
            <span v-if="!series.models.length" class="text-xs text-slate-400">台账中暂未填写具体型号</span>
          </div>
          <button class="scada-button w-full" type="button" @click="selectedSeries = series.value">
            查看系列设备 <ArrowRight :size="15" />
          </button>
        </div>
      </DataPanel>
    </div>

    <DataPanel title="型号台账" subtitle="型号、站点和运行状态均来自现有设备接口。">
      <div class="mb-4 grid gap-3 md:grid-cols-[220px_minmax(0,1fr)]">
        <select v-model="selectedSeries" class="scada-input">
          <option value="">全部产品系列</option>
          <option v-for="item in productSeriesOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <span class="relative">
          <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" :size="16" />
          <input v-model.trim="keyword" class="scada-input !pl-10" placeholder="搜索设备名称、编码、型号或站点" />
        </span>
      </div>
      <div v-if="filteredDevices.length" class="overflow-x-auto rounded-lg border border-slate-600/20">
        <table class="min-w-[760px]">
          <thead><tr><th>设备</th><th>厂家 / 系列</th><th>型号</th><th>站点位置</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="device in filteredDevices" :key="device.id">
              <td><div class="font-black text-white">{{ device.device_name }}</div><div class="mt-1 text-xs text-slate-400">{{ device.device_code || device.id }}</div></td>
              <td>{{ manufacturerLabel(device.manufacturer) }} / {{ device.product_series || '-' }}</td>
              <td class="font-bold text-cyan-200">{{ device.model || '未填写' }}</td>
              <td>{{ device.station_name || device.location || '-' }}</td>
              <td><StatusPill :value="device.status" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <EmptyState v-else title="没有匹配的设备" text="请调整系列或关键词；设备型号需要在设备台账中维护。" />
    </DataPanel>

    <PageNotice tone="warning" title="范围约束" message="新增厂家或产品系列需要同步后端模型、数据库与 API 契约。本页严格保留华为和阳光电源光伏逆变器范围。" />
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ArrowRight, ListTree, RefreshCcw, Search } from '@lucide/vue'
import { getDevicesApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import PageNotice from '@/components/PageNotice.vue'
import StatusPill from '@/components/StatusPill.vue'
import { productSeriesOptions } from '@/types'
import type { DeviceItem } from '@/types'

const devices = ref<DeviceItem[]>([])
const loading = ref(false)
const error = ref('')
const selectedSeries = ref('')
const keyword = ref('')

const seriesCards = computed(() => productSeriesOptions.map((item) => {
  const matches = devices.value.filter((device) => device.product_series === item.value)
  return {
    ...item,
    manufacturerLabel: manufacturerLabel(item.manufacturer),
    count: matches.length,
    activeCount: matches.filter((device) => !['offline', 'retired', 'disabled'].includes(device.status)).length,
    models: [...new Set(matches.map((device) => device.model).filter((value): value is string => Boolean(value)))],
    description: item.value === 'FusionSolar'
      ? '华为监控与运维生态标识，用于资料、设备和来源追溯的系列过滤。'
      : `${item.label} 系列光伏逆变器的设备、资料、诊断与检修任务归类入口。`
  }
}))

const filteredDevices = computed(() => {
  const query = keyword.value.toLowerCase()
  return devices.value.filter((device) => {
    if (selectedSeries.value && device.product_series !== selectedSeries.value) return false
    if (!query) return true
    return [device.device_name, device.device_code, device.model, device.station_name, device.location]
      .some((value) => value?.toLowerCase().includes(query))
  })
})

async function loadDevices() {
  loading.value = true
  error.value = ''
  try {
    const result = await getDevicesApi({ page: 1, page_size: 200, device_type: 'pv_inverter' })
    devices.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '设备台账统计读取失败'
    devices.value = []
  } finally {
    loading.value = false
  }
}

function manufacturerLabel(value?: string | null) {
  return value === 'huawei' ? '华为' : value === 'sungrow' ? '阳光电源' : value || '-'
}

onMounted(loadDevices)
</script>
