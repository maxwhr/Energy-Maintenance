<template>
  <PageFrame title="告警与故障类型" code="DEVICE / ALARM GUIDE" description="按厂家、产品系列和故障类型快速定位排查入口；页面只使用前后端约定枚举，不伪造厂商告警码。">
    <template #actions>
      <RouterLink class="scada-button primary" :to="diagnosisLink()">
        <Stethoscope :size="16" />
        进入故障诊断
      </RouterLink>
    </template>

    <PageNotice
      tone="info"
      title="数据边界"
      message="当前后端未提供独立厂商告警码库接口。本页提供规范故障分类、检索与诊断联动；具体告警代码请按设备面板或厂商手册原样输入。"
    />

    <DataPanel title="快速筛选" subtitle="首版范围仅限华为 SUN2000 / FusionSolar 与阳光电源 SG 系列。">
      <div class="grid gap-3 md:grid-cols-3">
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          厂家
          <select v-model="manufacturer" class="scada-input">
            <option value="">全部厂家</option>
            <option v-for="item in manufacturerOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          产品系列
          <select v-model="productSeries" class="scada-input">
            <option value="">全部系列</option>
            <option v-for="item in availableSeries" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          故障类型
          <span class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" :size="16" />
            <input v-model.trim="keyword" class="scada-input !pl-10" placeholder="搜索过温、通信、MPPT…" />
          </span>
        </label>
      </div>
    </DataPanel>

    <DataPanel title="标准故障分类" :subtitle="`共 ${filteredFaults.length} 项，点击可携带条件进入诊断页面。`">
      <div v-if="filteredFaults.length" class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <article v-for="item in filteredFaults" :key="item.value" class="group rounded-lg border border-slate-600/20 bg-black/20 p-4 transition hover:border-cyan-300/40">
          <div class="flex items-start justify-between gap-3">
            <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg" :class="faultMeta[item.value]?.tone || 'bg-cyan-400/10 text-cyan-200'">
              <AlertTriangle :size="18" />
            </div>
            <span class="rounded-full bg-slate-500/10 px-2 py-1 text-[11px] font-bold text-slate-400">{{ faultMeta[item.value]?.level || '需排查' }}</span>
          </div>
          <h3 class="mt-4 text-base font-black text-white">{{ item.label }}</h3>
          <p class="mt-1 font-mono text-[11px] text-cyan-200">{{ item.value }}</p>
          <p class="mt-3 min-h-10 text-xs leading-5 text-slate-400">{{ faultMeta[item.value]?.guide || '结合设备状态、告警代码与厂商资料进行辅助排查。' }}</p>
          <RouterLink class="mt-4 inline-flex items-center gap-1 text-sm font-black text-cyan-200 hover:text-cyan-100" :to="diagnosisLink(item.value)">
            带入诊断 <ArrowRight :size="15" />
          </RouterLink>
        </article>
      </div>
      <EmptyState v-else title="没有匹配的故障类型" text="请调整厂家、系列或搜索关键词。" />
    </DataPanel>

    <DataPanel title="现场使用建议" subtitle="先确认安全边界，再记录现象并进行辅助诊断。">
      <div class="grid gap-3 md:grid-cols-3">
        <div v-for="(step, index) in steps" :key="step.title" class="rounded-lg border border-slate-600/20 bg-black/20 p-4">
          <div class="text-xs font-black text-cyan-200">0{{ index + 1 }}</div>
          <div class="mt-2 font-black text-white">{{ step.title }}</div>
          <p class="mt-2 text-xs leading-5 text-slate-400">{{ step.text }}</p>
        </div>
      </div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { AlertTriangle, ArrowRight, Search, Stethoscope } from '@lucide/vue'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import PageNotice from '@/components/PageNotice.vue'
import { faultTypeOptions, manufacturerOptions, productSeriesOptions } from '@/types'

const manufacturer = ref('')
const productSeries = ref('')
const keyword = ref('')

const availableSeries = computed(() => productSeriesOptions.filter((item) => !manufacturer.value || item.manufacturer === manufacturer.value))
const filteredFaults = computed(() => {
  const query = keyword.value.toLowerCase()
  return faultTypeOptions.filter((item) => !query || item.label.toLowerCase().includes(query) || item.value.toLowerCase().includes(query))
})

watch(manufacturer, () => {
  if (!availableSeries.value.some((item) => item.value === productSeries.value)) productSeries.value = ''
})

const faultMeta: Record<string, { level: string; guide: string; tone: string }> = {
  low_insulation_resistance: { level: '高风险', guide: '关注直流侧绝缘、组串接地与潮湿环境，操作前落实停电验电。', tone: 'bg-red-500/10 text-red-200' },
  dc_abnormal: { level: '重点排查', guide: '核对组串电压、电流、接线极性和直流开关状态。', tone: 'bg-amber-400/10 text-amber-100' },
  ac_overvoltage: { level: '并网异常', guide: '核对电网电压、并网点参数和保护阈值，禁止擅自修改保护设置。', tone: 'bg-amber-400/10 text-amber-100' },
  ac_undervoltage: { level: '并网异常', guide: '检查交流侧电压、断路器、线缆和电网波动记录。', tone: 'bg-amber-400/10 text-amber-100' },
  grid_connection_fault: { level: '并网异常', guide: '结合电网频率、电压、相序和并网保护信息综合判断。', tone: 'bg-red-500/10 text-red-200' },
  over_temperature: { level: '需降载关注', guide: '检查散热通道、环境温度、风扇状态和设备积尘。', tone: 'bg-amber-400/10 text-amber-100' },
  fan_fault: { level: '维护建议', guide: '确认风扇堵转、异响、供电和寿命状态，按手册要求更换。', tone: 'bg-cyan-400/10 text-cyan-200' },
  communication_interruption: { level: '通信异常', guide: '检查通信线缆、采集器、地址配置和平台在线状态。', tone: 'bg-cyan-400/10 text-cyan-200' },
  device_offline: { level: '离线', guide: '先确认设备供电和通信链路，再排查平台侧连接状态。', tone: 'bg-slate-500/10 text-slate-400' },
  mppt_abnormal: { level: '发电异常', guide: '比较各 MPPT 支路电压电流，排查遮挡、失配和组串异常。', tone: 'bg-amber-400/10 text-amber-100' },
  low_power_generation: { level: '性能异常', guide: '结合辐照、温度、组串状态、限发记录和历史曲线排查。', tone: 'bg-cyan-400/10 text-cyan-200' },
  alarm_code_query: { level: '代码查询', guide: '保留完整告警代码、发生时间和设备型号，以便检索厂商资料。', tone: 'bg-cyan-400/10 text-cyan-200' }
}

const steps = [
  { title: '记录现场', text: '记录设备型号、完整告警代码、发生时间、运行状态与环境条件。' },
  { title: '确认安全', text: '遵循厂商手册和电气作业规程，未经授权不得带电拆检或调整保护参数。' },
  { title: '辅助诊断', text: '将故障类型与现场描述带入诊断，核对真实引用后再由工程师决策。' }
]

function diagnosisLink(faultType = '') {
  return {
    path: '/diagnosis',
    query: {
      ...(manufacturer.value ? { manufacturer: manufacturer.value } : {}),
      ...(productSeries.value ? { product_series: productSeries.value } : {}),
      ...(faultType ? { fault_type: faultType } : {})
    }
  }
}
</script>
