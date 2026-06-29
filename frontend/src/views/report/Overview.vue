<template>
  <PageFrame title="统计报表" code="REPORT / OVERVIEW" description="读取后端系统统计接口展示业务数据，不使用前端固定指标。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadStatistics">刷新</button>
    </template>
    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>
    <DataPanel title="后端统计">
      <div v-if="statisticSections.length" class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <section v-for="section in statisticSections" :key="section.label" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">{{ section.label }}</h3>
          <div class="mt-3 space-y-2">
            <div v-for="item in section.items" :key="item.key" class="flex items-center justify-between gap-3 text-xs">
              <span class="text-slate-400">{{ item.label }}</span>
              <span class="font-mono text-slate-100">{{ item.value }}</span>
            </div>
          </div>
        </section>
      </div>
      <div v-else class="text-sm text-slate-400">暂无统计数据</div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getSystemStatisticsApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import type { SystemStatistics } from '@/types'
import { formatMetricLabel, formatMetricSectionLabel } from '@/utils/display'

const statistics = ref<SystemStatistics | null>(null)
const loading = ref(false)
const error = ref('')
const statisticSections = computed(() => {
  if (!statistics.value) return []
  return Object.entries(statistics.value)
    .filter(([, value]) => value && typeof value === 'object' && !Array.isArray(value))
    .map(([key, value]) => ({
      label: formatMetricSectionLabel(key),
      items: Object.entries(value as Record<string, unknown>).map(([key, itemValue]) => ({
        key,
        label: formatMetricLabel(key),
        value: String(itemValue ?? '-')
      }))
    }))
})

async function loadStatistics() {
  loading.value = true
  error.value = ''
  try {
    statistics.value = await getSystemStatisticsApi()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '统计数据读取失败'
    statistics.value = null
  } finally {
    loading.value = false
  }
}

onMounted(loadStatistics)
</script>
