<template>
  <DataPanel class="h-full overflow-hidden" title="光伏逆变器运行拓扑" subtitle="华为与阳光电源光伏逆变器检修态势">
    <template #actions>
      <div class="flex items-center gap-1">
        <button class="scada-button !min-h-8 !px-2" type="button" @click="zoom += 0.08" title="放大">
          <ZoomIn :size="16" />
        </button>
        <button class="scada-button !min-h-8 !px-2" type="button" @click="zoom = Math.max(0.7, zoom - 0.08)" title="缩小">
          <ZoomOut :size="16" />
        </button>
        <button class="scada-button !min-h-8 !px-2" type="button" @click="reset" title="复位">
          <Move :size="16" />
        </button>
      </div>
    </template>

    <div
      class="synoptic-grid relative h-[360px] overflow-hidden rounded-md border border-slate-600/25 bg-[#05080d]"
      @wheel.prevent="onWheel"
    >
      <div class="absolute left-3 top-3 z-10 rounded border border-[#cbd9e7] bg-white/90 px-2 py-1 font-mono text-xs text-[#195FA8]">
        逆变器 {{ offset.x }} / 组串 {{ offset.y }} / 缩放 {{ zoomText }}
      </div>
      <svg
        class="absolute left-1/2 top-1/2 h-[320px] w-[720px] max-w-none origin-center transition-transform duration-150"
        :style="{ transform: `translate(calc(-50% + ${offset.x}px), calc(-50% + ${offset.y}px)) scale(${zoom})` }"
        viewBox="0 0 720 320"
        role="img"
        aria-label="光伏逆变器检修拓扑图"
      >
        <defs>
          <filter id="glow">
            <feGaussianBlur stdDeviation="2.2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        <rect x="18" y="28" width="684" height="264" rx="4" fill="#f8fbfe" stroke="#cbd9e7" />
        <path d="M80 160H640" stroke="#8fb0cf" stroke-width="8" stroke-linecap="round" />
        <path d="M148 160V80H262" stroke="#8fb0cf" stroke-width="5" fill="none" />
        <path d="M148 160V242H262" stroke="#8fb0cf" stroke-width="5" fill="none" />
        <path d="M360 160V78H500" stroke="#8fb0cf" stroke-width="5" fill="none" />
        <path d="M360 160V242H500" stroke="#8fb0cf" stroke-width="5" fill="none" />
        <g v-for="node in nodes" :key="node.id" :filter="node.status === 'fault' ? 'url(#glow)' : undefined">
          <rect :x="node.x" :y="node.y" width="124" height="54" rx="4" :fill="nodeFill(node.status)" :stroke="nodeStroke(node.status)" stroke-width="2" />
          <text :x="node.x + 12" :y="node.y + 22" fill="#172538" font-size="13" font-weight="700">{{ node.name }}</text>
          <text :x="node.x + 12" :y="node.y + 42" :fill="nodeText(node.status)" font-size="12">{{ node.value }}</text>
        </g>
        <g>
          <circle cx="80" cy="160" r="15" fill="#ffffff" stroke="#195fa8" stroke-width="2" />
          <circle cx="640" cy="160" r="15" fill="#ffffff" stroke="#23a55a" stroke-width="2" />
          <text x="48" y="198" fill="#53697f" font-size="12">组件串列</text>
          <text x="604" y="198" fill="#53697f" font-size="12">并网点</text>
        </g>
      </svg>
      <div class="absolute bottom-3 right-3 text-right text-xs text-slate-500">工业运维视图</div>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Move, ZoomIn, ZoomOut } from '@lucide/vue'
import DataPanel from '@/components/DataPanel.vue'

const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const zoomText = computed(() => `${Math.round(zoom.value * 100)}%`)

const nodes = [
  { id: 'huawei-sun2000', name: '华为 SUN2000', value: '在线', status: 'online', x: 82, y: 52 },
  { id: 'fusion-solar', name: 'FusionSolar', value: '告警同步', status: 'warning', x: 252, y: 52 },
  { id: 'sungrow-sg', name: '阳光 SG', value: '正常发电', status: 'online', x: 252, y: 216 },
  { id: 'knowledge', name: '检修知识库', value: '来源追溯', status: 'online', x: 494, y: 52 },
  { id: 'fault', name: '告警排查', value: '待确认', status: 'fault', x: 494, y: 216 }
]

function nodeFill(status: string) {
  if (status === 'fault') return '#fff1f2'
  if (status === 'warning') return '#fff7ed'
  return '#eef6ff'
}

function nodeStroke(status: string) {
  if (status === 'fault') return '#d63b3b'
  if (status === 'warning') return '#c76013'
  return '#195fa8'
}

function nodeText(status: string) {
  if (status === 'fault') return '#b4232f'
  if (status === 'warning') return '#c76013'
  return '#195fa8'
}

function onWheel(event: WheelEvent) {
  zoom.value = Math.min(1.55, Math.max(0.75, zoom.value + (event.deltaY > 0 ? -0.04 : 0.04)))
}

function reset() {
  zoom.value = 1
  offset.value = { x: 0, y: 0 }
}
</script>
