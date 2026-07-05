<template>
  <DataPanel :title="text.title" :subtitle="text.subtitle">
    <div v-if="approvals.length" class="space-y-3">
      <article v-for="item in approvals" :key="item.id" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="font-black text-white">{{ item.approval_type }}</span>
          <MultimodalStatusPill :value="item.status" />
        </div>
        <p class="mt-2 text-sm text-slate-300">{{ item.requested_action }}</p>
        <p v-if="item.review_comment" class="mt-2 text-xs text-cyan-100">{{ item.review_comment }}</p>
        <div v-if="canReview && item.status === 'pending'" class="mt-3 flex flex-wrap gap-2">
          <button
            class="scada-button primary"
            type="button"
            :data-testid="`approve-${item.approval_type}`"
            @click="$emit('approve', item.id)"
          >
            {{ text.approve }}
          </button>
          <button
            class="scada-button danger"
            type="button"
            :data-testid="`reject-${item.approval_type}`"
            @click="$emit('reject', item.id)"
          >
            {{ text.reject }}
          </button>
        </div>
      </article>
    </div>
    <div v-else class="rounded-md border border-slate-600/20 bg-black/20 p-4 text-sm text-slate-400">
      {{ text.empty }}
    </div>
  </DataPanel>
</template>

<script setup lang="ts">
import DataPanel from '@/components/DataPanel.vue'
import MultimodalStatusPill from '@/components/MultimodalStatusPill.vue'
import type { AgentApproval } from '@/types/agent'

withDefaults(defineProps<{ approvals: AgentApproval[]; canReview?: boolean }>(), { canReview: false })
defineEmits<{ approve: [approvalId: string]; reject: [approvalId: string] }>()

const text = {
  title: '\u5ba1\u6279\u8bb0\u5f55',
  subtitle: '\u9700\u8981\u4eba\u5de5\u786e\u8ba4\u7684\u52a8\u4f5c\u5728\u8fd9\u91cc\u8ffd\u8e2a\u3002',
  approve: '\u901a\u8fc7\u8349\u7a3f',
  reject: '\u9a73\u56de\u8349\u7a3f',
  empty: '\u6682\u65e0\u5ba1\u6279\u8bb0\u5f55\u3002'
}
</script>
