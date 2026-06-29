<template>
  <PageFrame title="告警类型" code="DEVICE / FAULT TYPES" description="展示第一版光伏逆变器故障类型枚举，诊断与检索会把这些值提交给后端。">
    <DataPanel title="第一版故障类型" subtitle="此页仅展示前后端约定枚举，不伪造独立告警码库数据。">
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <div v-for="item in faultTypeOptions" :key="item.value" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="font-black text-white">{{ item.label }}</div>
          <div class="mt-2 font-mono text-xs text-cyan-200">{{ item.value }}</div>
        </div>
      </div>
    </DataPanel>
    <DataPanel title="使用说明">
      <p class="text-sm leading-7 text-slate-300">
        告警代码请在检修问答或故障诊断页面输入。若后端后续提供厂家告警码库接口，可在保持第一版厂家范围的前提下扩展此页。
      </p>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { faultTypeOptions } from '@/types'
</script>
