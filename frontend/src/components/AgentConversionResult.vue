<template>
  <DataPanel v-if="convertibleItems.length" :title="text.panelTitle" :subtitle="text.panelSubtitle">
    <div class="space-y-3">
      <article
        v-for="item in convertibleItems"
        :key="item.artifact.id"
        class="rounded-md border border-slate-600/20 bg-black/20 p-3"
      >
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div class="text-xs font-bold text-slate-400">{{ item.artifact.artifact_type }}</div>
            <h3 class="mt-1 font-black text-white">{{ item.title }}</h3>
            <p class="mt-1 text-sm text-slate-300">{{ item.description }}</p>
          </div>
          <span class="rounded border border-cyan-300/20 bg-cyan-400/10 px-2 py-1 text-xs font-bold text-cyan-100">
            {{ targetLabel(item.targetType) }}
          </span>
        </div>

        <div
          v-if="item.status?.converted_targets?.[item.targetType]"
          class="mt-3 rounded-md border border-emerald-300/20 bg-emerald-400/10 p-3 text-sm text-emerald-100"
        >
          {{ text.converted }}{{ item.status.converted_targets[item.targetType]?.target_id }}
          <div class="mt-1 break-all font-mono text-xs">
            {{ item.status.converted_targets[item.targetType]?.conversion_trace_id }}
          </div>
        </div>

        <div
          v-else-if="item.status?.blocked_reason"
          class="mt-3 rounded-md border border-amber-300/20 bg-amber-400/10 p-3 text-sm text-amber-100"
        >
          <div class="font-bold">{{ blockedLabel(item.status.blocked_reason) }}</div>
          <div class="mt-1 text-xs">{{ item.status.message || text.duplicateNote }}</div>
        </div>

        <div v-else class="mt-3 grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <div class="space-y-2 text-xs text-slate-300">
            <p>{{ text.approvalStatus }}{{ item.approval?.status || item.status?.approval_status || 'not_found' }}</p>
            <p v-if="item.risky" class="rounded border border-amber-300/30 bg-amber-400/10 p-2 text-amber-100">
              {{ text.riskWarning }}
            </p>
            <label v-if="item.risky && isAdmin && canConvert" class="flex items-center gap-2">
              <input v-model="overrideWarnings[item.key]" type="checkbox" />
              <span>{{ text.adminOverride }}</span>
            </label>
          </div>
          <button
            v-if="canConvert"
            class="scada-button primary"
            type="button"
            :data-testid="`convert-${item.targetType}`"
            :disabled="busy || item.status?.can_convert === false || item.approval?.status !== 'approved' || (item.risky && !overrideWarnings[item.key])"
            @click="$emit('convert', item.artifact.id, item.targetType, item.approval?.id || item.status?.approval_id || '', Boolean(overrideWarnings[item.key]))"
          >
            {{ buttonLabel(item.targetType) }}
          </button>
        </div>

        <div
          v-if="item.status?.conversions?.length"
          class="mt-3 rounded-md border border-slate-600/20 bg-black/20 p-3"
          :data-testid="`conversion-history-${item.targetType}`"
        >
          <div class="text-xs font-bold text-slate-400">{{ text.historyTitle }}</div>
          <div class="mt-2 space-y-2">
            <div v-for="history in item.status.conversions" :key="history.conversion_trace_id" class="rounded bg-black/30 p-2 text-xs text-slate-200">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <span class="font-bold text-white">{{ statusLabel(history.conversion_status || history.status) }}</span>
                <span class="font-mono text-cyan-100">{{ history.conversion_trace_id }}</span>
              </div>
              <div class="mt-1 break-all text-slate-300">target_id：{{ history.target_id || '-' }}</div>
              <div class="mt-1 text-slate-400">completed_at：{{ formatTime(history.completed_at || history.converted_at) }}</div>
              <div v-if="history.error_message" class="mt-1 text-red-200">{{ history.error_message }}</div>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="results.length" class="mt-4 rounded-md border border-slate-600/20 bg-black/20 p-3">
      <div class="text-xs font-bold text-slate-400">{{ text.latestResult }}</div>
      <div class="mt-2 grid gap-2">
        <div v-for="item in results" :key="item.conversion_trace_id" class="rounded bg-black/30 p-2 text-sm text-slate-200">
          <div class="font-bold text-white">{{ targetLabel(item.target_type) }}: {{ item.target_id }}</div>
          <div class="break-all font-mono text-xs text-cyan-100">{{ item.conversion_trace_id }}</div>
          <div class="text-xs text-slate-400">{{ statusLabel(item.conversion_status || item.status) }}</div>
          <p class="mt-1 text-xs text-slate-300">{{ item.message }}</p>
          <ul v-if="item.warnings?.length" class="mt-1 list-disc pl-5 text-xs text-amber-100">
            <li v-for="warning in item.warnings" :key="warning">{{ warning }}</li>
          </ul>
        </div>
      </div>
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import type {
  AgentApproval,
  AgentArtifact,
  AgentArtifactConversionResult,
  AgentArtifactConversionStatus,
  AgentConversionTargetType
} from '@/types/agent'

const props = defineProps<{
  artifacts: AgentArtifact[]
  approvals: AgentApproval[]
  statuses: Record<string, AgentArtifactConversionStatus | undefined>
  results: AgentArtifactConversionResult[]
  canConvert: boolean
  isAdmin: boolean
  busy?: boolean
}>()

defineEmits<{
  convert: [artifactId: string, targetType: AgentConversionTargetType, approvalId: string, overrideWarnings: boolean]
}>()

const overrideWarnings = reactive<Record<string, boolean>>({})

const text = {
  panelTitle: '\u8349\u7a3f\u8f6c\u6b63\u5f0f\u5bf9\u8c61',
  panelSubtitle: '\u5ba1\u6279\u901a\u8fc7\u540e\u7531 expert/admin \u624b\u52a8\u89e6\u53d1\uff1b\u8f6c\u6362\u7ed3\u679c\u7531\u540e\u7aef API \u6301\u4e45\u5316\u5e76\u5199\u5165\u5ba1\u8ba1\u4e8b\u4ef6\u3002',
  converted: '\u5df2\u8f6c\u6362\uff1a',
  duplicateNote: '\u5df2\u5b58\u5728\u8f6c\u6362\u8bb0\u5f55\uff0c\u540e\u7aef\u4e0d\u4f1a\u91cd\u590d\u521b\u5efa\u6b63\u5f0f\u5bf9\u8c61\u3002',
  approvalStatus: '\u5ba1\u6279\u72b6\u6001\uff1a',
  riskWarning: '\u5f53\u524d\u8349\u7a3f\u5305\u542b mocked \u6216\u672a\u590d\u6838 AI \u8bc1\u636e\uff0cexpert \u9ed8\u8ba4\u963b\u65ad\uff0cadmin \u53ef\u52fe\u9009 override \u540e\u63d0\u4ea4\u3002',
  adminOverride: 'admin override \u98ce\u9669\u8fb9\u754c',
  latestResult: '\u672c\u6b21\u8f6c\u6362\u7ed3\u679c',
  historyTitle: '\u8f6c\u6362\u5386\u53f2',
  defaultDescription: '\u5ba1\u6279\u901a\u8fc7\u540e\u53ef\u624b\u52a8\u8f6c\u6362\u4e3a\u6b63\u5f0f\u4e1a\u52a1\u5bf9\u8c61\u3002'
}

const targetByArtifactType: Partial<Record<string, AgentConversionTargetType>> = {
  knowledge_contribution_draft: 'knowledge_contribution',
  sop_draft: 'sop_template',
  task_draft: 'maintenance_task',
  kg_candidate_suggestion: 'kg_candidate'
}

const approvalTypeByArtifactType: Record<string, string> = {
  knowledge_contribution_draft: 'knowledge_contribution_draft_review',
  sop_draft: 'sop_draft_review',
  task_draft: 'task_draft_review',
  kg_candidate_suggestion: 'knowledge_contribution_draft_review'
}

const convertibleItems = computed(() =>
  props.artifacts
    .map((artifact) => {
      const targetType = targetByArtifactType[artifact.artifact_type]
      if (!targetType) return null
      const approval = props.approvals.find((item) => item.approval_type === approvalTypeByArtifactType[artifact.artifact_type])
      const status = props.statuses[artifact.id]
      const key = `${artifact.id}:${targetType}`
      return {
        key,
        artifact,
        targetType,
        approval,
        status,
        title: artifact.title || artifact.artifact_type,
        description: artifact.content_text || text.defaultDescription,
        risky: isRisky(artifact.content_json || {})
      }
    })
    .filter(Boolean) as Array<{
      key: string
      artifact: AgentArtifact
      targetType: AgentConversionTargetType
      approval?: AgentApproval
      status?: AgentArtifactConversionStatus
      title: string
      description: string
      risky: boolean
    }>
)

function isRisky(value: Record<string, unknown>) {
  const boundary = value.evidence_boundary as Record<string, unknown> | undefined
  return Boolean(
    value.mocked_evidence_used ||
      value.unreviewed_ai_evidence_used ||
      boundary?.mocked_evidence_used ||
      boundary?.unreviewed_ai_evidence_used
  )
}

function targetLabel(value: AgentConversionTargetType) {
  const labels: Record<AgentConversionTargetType, string> = {
    knowledge_contribution: '\u6b63\u5f0f\u77e5\u8bc6\u8d21\u732e',
    sop_template: 'SOP \u6a21\u677f',
    maintenance_task: '\u68c0\u4fee\u4efb\u52a1',
    kg_candidate: '\u56fe\u8c31\u5019\u9009'
  }
  return labels[value]
}

function buttonLabel(value: AgentConversionTargetType) {
  const labels: Record<AgentConversionTargetType, string> = {
    knowledge_contribution: '\u8f6c\u4e3a\u6b63\u5f0f\u77e5\u8bc6\u8d21\u732e',
    sop_template: '\u8f6c\u4e3a SOP \u6a21\u677f',
    maintenance_task: '\u8f6c\u4e3a\u68c0\u4fee\u4efb\u52a1',
    kg_candidate: '\u8f6c\u4e3a\u56fe\u8c31\u5019\u9009'
  }
  return labels[value]
}

function statusLabel(value?: string | null) {
  const labels: Record<string, string> = {
    pending: '\u5f85\u8f6c\u6362',
    converting: '\u8f6c\u6362\u4e2d',
    succeeded: '\u5df2\u6210\u529f',
    failed: '\u8f6c\u6362\u5931\u8d25',
    voided: '\u5df2\u4f5c\u5e9f',
    already_converted: '\u5df2\u8f6c\u6362',
    conversion_in_progress: '\u8f6c\u6362\u8fdb\u884c\u4e2d'
  }
  return labels[value || ''] || value || '-'
}

function blockedLabel(value?: string | null) {
  const labels: Record<string, string> = {
    already_converted: '\u5df2\u8f6c\u6362\uff0c\u4e0d\u4f1a\u91cd\u590d\u521b\u5efa\u6b63\u5f0f\u5bf9\u8c61',
    conversion_in_progress: '\u8f6c\u6362\u6b63\u5728\u8fdb\u884c\uff0c\u8bf7\u7a0d\u540e\u5237\u65b0',
    approval_missing: '\u9700\u8981\u5148\u5b8c\u6210\u5ba1\u6279',
    approval_pending: '\u5ba1\u6279\u672a\u901a\u8fc7',
    approval_rejected: '\u5ba1\u6279\u5df2\u9a73\u56de',
    previous_conversion_failed: '\u4e0a\u6b21\u8f6c\u6362\u5931\u8d25\uff0c\u9700\u7ba1\u7406\u5458\u5904\u7406',
    conversion_voided: '\u8f6c\u6362\u8bb0\u5f55\u5df2\u4f5c\u5e9f'
  }
  return labels[value || ''] || value || '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}
</script>
