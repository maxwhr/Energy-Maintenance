<template>
  <DataPanel v-if="draft" title="知识贡献草稿" subtitle="仅为待审核草稿，未创建正式知识贡献、文档或切片。">
    <div class="grid gap-3 lg:grid-cols-[300px_minmax(0,1fr)]">
      <section class="rounded-md border border-cyan-300/20 bg-cyan-400/10 p-3">
        <div class="text-xs font-bold text-cyan-100">草稿标题</div>
        <h3 class="mt-2 text-lg font-black text-white">{{ text(draft.title) }}</h3>
        <p class="mt-2 text-sm text-slate-200">{{ text(draft.problem_description) }}</p>
        <div class="mt-3 flex flex-wrap gap-2">
          <span class="rounded border border-cyan-200/20 px-2 py-1 text-xs text-cyan-100">{{ text(draft.category) }}</span>
          <span class="rounded border border-cyan-200/20 px-2 py-1 text-xs text-cyan-100">质量 {{ text(draft.draft_quality_score) }}</span>
        </div>
      </section>
      <section class="grid gap-3 md:grid-cols-2">
        <ListBlock title="排查步骤" :items="troubleshootingSteps" />
        <ListBlock title="安全措施" :items="safetyPrecautions" />
        <ListBlock title="适用条件" :items="applicableConditions" />
        <ListBlock title="不适用条件" :items="notApplicableConditions" />
      </section>
    </div>

    <div class="mt-3 grid gap-3 md:grid-cols-3">
      <div class="rounded-md border border-amber-300/20 bg-amber-400/10 p-3">
        <div class="text-xs font-bold text-amber-100">重复风险</div>
        <p class="mt-2 text-sm text-slate-200">{{ duplicateText }}</p>
        <p class="mt-2 text-xs text-amber-100">
          模式：{{ text(duplicateRisk?.duplicate_check_mode) }} / vector_backend：{{ text(duplicateRisk?.vector_backend) }}
        </p>
        <p class="mt-1 text-xs text-amber-100">max_similarity：{{ text(duplicateRisk?.max_similarity) }}</p>
      </div>
      <div class="rounded-md border border-red-300/20 bg-red-400/10 p-3">
        <div class="text-xs font-bold text-red-100">证据边界</div>
        <p class="mt-2 text-sm text-slate-200">
          mock：{{ draft.mocked_evidence_used ? '包含' : '未包含' }}；
          未审 AI：{{ draft.unreviewed_ai_evidence_used ? '包含' : '未包含' }}
        </p>
      </div>
      <div class="rounded-md border border-slate-500/20 bg-black/20 p-3">
        <div class="text-xs font-bold text-slate-300">正式写入</div>
        <p class="mt-2 text-sm text-slate-200">未创建正式知识贡献、知识文档或 approved chunks。</p>
      </div>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import ListBlock from '@/components/MultimodalListBlock.vue'

const props = defineProps<{ draft?: Record<string, unknown> | null }>()

const troubleshootingSteps = computed(() => toTextList(props.draft?.troubleshooting_steps))
const safetyPrecautions = computed(() => toTextList(props.draft?.safety_precautions))
const applicableConditions = computed(() => toTextList(props.draft?.applicable_conditions))
const notApplicableConditions = computed(() => toTextList(props.draft?.not_applicable_conditions))
const duplicateRisk = computed(() => props.draft?.duplicate_risk as Record<string, unknown> | undefined)

const duplicateText = computed(() => {
  const risk = duplicateRisk.value
  if (!risk) return '未返回重复风险信息'
  return risk.has_similar_knowledge ? '可能存在相似已审核知识，需专家确认。' : '当前检索未发现明显相似知识。'
})

function text(value: unknown) {
  return value == null || value === '' ? '-' : String(value)
}

function toTextList(value: unknown) {
  return Array.isArray(value)
    ? value.map((item) => typeof item === 'string' ? item : JSON.stringify(item)).filter(Boolean)
    : []
}
</script>
