<template>
  <PageFrame
    title="运行总览"
    code="SCREEN / DASHBOARD"
    description="汇总华为与阳光电源光伏逆变器台账、检修任务、知识文档和记录追溯状态。"
  >
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadDashboard">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">
      {{ error }}
    </div>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_420px]">
      <SynopticBoard />
      <div class="grid gap-4">
        <DataPanel title="实时指标">
          <div class="grid grid-cols-2 gap-3">
            <div v-for="metric in metrics" :key="metric.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
              <div class="text-xs font-bold text-slate-400">{{ metric.label }}</div>
              <div class="mt-2 text-2xl font-black text-white">{{ metric.value }}</div>
              <div class="mt-1 font-mono text-xs" :class="metric.tone">{{ metric.delta }}</div>
            </div>
          </div>
        </DataPanel>
        <DataPanel title="厂家分布">
          <div class="space-y-3">
            <div v-for="item in manufacturerStats" :key="item.label" class="flex items-center justify-between rounded-md bg-white/[0.03] px-3 py-2">
              <div>
                <div class="text-sm font-black text-slate-100">{{ item.label }}</div>
                <div class="text-xs text-slate-400">{{ item.code }}</div>
              </div>
              <div class="text-xl font-black text-white">{{ item.value }}</div>
            </div>
          </div>
        </DataPanel>
      </div>
    </div>

    <div class="grid gap-4 lg:grid-cols-3">
      <DataPanel title="近期检修任务">
        <div v-if="recentTasks.length" class="space-y-3">
          <RouterLink v-for="item in recentTasks" :key="item.id" :to="`/workorder/${item.id}`" class="block rounded-md border border-slate-600/20 bg-black/20 p-3 transition hover:border-cyan-300/40">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="font-bold text-white">{{ item.title }}</div>
                <div class="mt-1 text-xs text-slate-400">{{ item.device_name || '未绑定设备' }} / {{ labelOf(item.fault_type) }}</div>
              </div>
              <StatusPill :value="item.task_status || item.status" />
            </div>
          </RouterLink>
        </div>
        <EmptyState v-else text="暂无检修任务" />
      </DataPanel>
      <DataPanel title="最近知识文档">
        <div v-if="recentDocuments.length" class="space-y-3">
          <div v-for="doc in recentDocuments" :key="doc.id" class="rounded-md bg-white/[0.03] p-3">
            <div class="font-bold text-slate-100">{{ doc.title }}</div>
            <div class="mt-1 flex items-center justify-between gap-3 text-xs text-slate-400">
              <span>{{ labelOf(doc.document_type) }} / {{ labelOf(doc.product_series) }}</span>
              <StatusPill :value="doc.parse_status" />
            </div>
          </div>
        </div>
        <EmptyState v-else text="暂无知识文档" />
      </DataPanel>
      <DataPanel title="快速动作">
        <div class="grid gap-2">
          <RouterLink v-if="canOperate" class="scada-button justify-start" to="/assistant/chat"><Bot :size="17" /> 打开检修问答</RouterLink>
          <RouterLink v-if="canOperate" class="scada-button justify-start" to="/workorder/create"><Plus :size="17" /> 新建检修任务</RouterLink>
          <RouterLink v-if="canOperate" class="scada-button justify-start" to="/knowledge/search"><Search :size="17" /> 检索知识库</RouterLink>
          <div v-if="!canOperate" class="rounded-md border border-slate-600/20 bg-white/[0.03] px-3 py-3 text-sm text-slate-400">
            当前账号为只读角色，仅展示运行总览。
          </div>
        </div>
      </DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Bot, Plus, RefreshCcw, Search } from '@lucide/vue'
import { getDashboardStatsApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import SynopticBoard from '@/components/SynopticBoard.vue'
import { useUserStore } from '@/stores/user'
import type { DeviceStatistics, KnowledgeDocument, MaintenanceTask, SystemStatistics } from '@/types'

const userStore = useUserStore()
const loading = ref(false)
const error = ref('')
const systemStats = ref<SystemStatistics | null>(null)
const deviceStats = ref<DeviceStatistics | null>(null)
const taskStats = ref<Record<string, number>>({})
const recentTasks = ref<MaintenanceTask[]>([])
const recentDocuments = ref<KnowledgeDocument[]>([])

const metrics = computed(() => [
  { label: '逆变器总数', value: deviceStats.value?.total_devices ?? 0, delta: '设备台账', tone: 'text-cyan-200' },
  { label: '故障设备', value: deviceStats.value?.fault_devices ?? 0, delta: '当前告警', tone: 'text-red-300' },
  { label: '检修任务', value: sumTaskCount.value, delta: '任务闭环', tone: 'text-amber-200' },
  { label: '知识切片', value: Number(systemStats.value?.knowledge?.chunks ?? systemStats.value?.knowledge?.chunk_count ?? 0), delta: '知识库切片', tone: 'text-emerald-200' }
])

const manufacturerStats = computed(() => [
  { label: '华为', code: 'SUN2000 / FusionSolar', value: deviceStats.value?.huawei_devices ?? 0 },
  { label: '阳光电源', code: 'SG 系列', value: deviceStats.value?.sungrow_devices ?? 0 }
])

const sumTaskCount = computed(() => {
  const values = Object.values(taskStats.value).filter((value) => typeof value === 'number')
  return values.reduce((sum, value) => sum + value, 0)
})

const canOperate = computed(() => userStore.roles.some((role) => ['admin', 'expert', 'engineer'].includes(role)))

async function loadDashboard() {
  loading.value = true
  error.value = ''
  try {
    const data = await getDashboardStatsApi()
    systemStats.value = data.system
    deviceStats.value = data.deviceStats
    taskStats.value = data.taskStats
    recentTasks.value = data.recentTasks
    recentDocuments.value = data.recentDocuments
  } catch (err) {
    error.value = err instanceof Error ? err.message : '无法读取后端仪表盘数据'
    recentTasks.value = []
    recentDocuments.value = []
  } finally {
    loading.value = false
  }
}

function labelOf(value?: string | null) {
  const map: Record<string, string> = {
    huawei: '华为',
    sungrow: '阳光电源',
    pv_inverter: '光伏逆变器',
    manual: '设备手册',
    alarm_code: '告警代码',
    sop: '检修规程',
    fault_case: '故障案例',
    inspection_standard: '巡检规范',
    maintenance_record: '检修记录',
    over_temperature: '过温',
    fan_fault: '风扇故障',
    communication_interruption: '通信中断',
    device_offline: '设备离线',
    unknown: '未知'
  }
  return value ? map[value] ?? value : '未指定'
}

onMounted(loadDashboard)
</script>
