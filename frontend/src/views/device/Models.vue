<template>
  <PageFrame title="产品系列" code="DEVICE / SERIES" description="第一版仅开放华为 SUN2000、FusionSolar 与阳光电源 SG 系列。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadDevices">
        <RefreshCcw :size="16" />
        刷新台账统计
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 lg:grid-cols-3">
      <DataPanel v-for="series in seriesCards" :key="series.value" :title="series.label" :subtitle="series.manufacturerLabel">
        <div class="space-y-4">
          <div class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="text-xs font-bold text-slate-400">台账设备数</div>
            <div class="mt-2 text-3xl font-black text-white">{{ series.count }}</div>
          </div>
          <div class="text-sm leading-7 text-slate-300">{{ series.description }}</div>
        </div>
      </DataPanel>
    </div>

    <DataPanel title="说明" subtitle="此页不创建新的设备类型，只展示第一版允许的产品系列。">
      <p class="text-sm leading-7 text-slate-300">
        如果需要新增厂家或系列，应先经过后端模型、数据库迁移和 API 契约评审。本任务保持第一版范围不扩展。
      </p>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshCcw } from '@lucide/vue'
import { getDevicesApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { productSeriesOptions } from '@/types'
import type { DeviceItem } from '@/types'

const devices = ref<DeviceItem[]>([])
const loading = ref(false)
const error = ref('')

const seriesCards = computed(() =>
  productSeriesOptions.map((item) => ({
    ...item,
    manufacturerLabel: item.manufacturer === 'huawei' ? '华为' : '阳光电源',
    count: devices.value.filter((device) => device.product_series === item.value).length,
    description:
      item.value === 'FusionSolar'
        ? '作为华为运维生态标识，用于检修资料、告警排查和来源追溯的系列过滤。'
        : `${item.label} 系列光伏逆变器检修资料与任务台账过滤入口。`
  }))
)

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

onMounted(loadDevices)
</script>
