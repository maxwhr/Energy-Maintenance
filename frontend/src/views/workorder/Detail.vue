<template>
  <PageFrame title="任务详情" code="TASK / DETAIL" description="查看检修任务详情、维护任务信息并执行权限允许的状态流转。">
    <template #actions>
      <RouterLink class="scada-button" to="/workorder/list">返回列表</RouterLink>
      <button v-if="canEdit" class="scada-button" type="button" @click="openEdit">
        <Pencil :size="16" />
        编辑任务
      </button>
      <button v-if="canReassign" class="scada-button" type="button" @click="openAssign">
        <UserRoundCog :size="16" />
        重新分派
      </button>
      <button class="scada-button" type="button" :disabled="loading" @click="loadDetail">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div v-if="task" class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <DataPanel title="任务信息">
        <div class="space-y-4">
          <div>
            <h2 class="text-xl font-black text-white">{{ task.title }}</h2>
            <p class="mt-2 text-sm leading-7 text-slate-300">{{ task.fault_description || '未填写故障描述' }}</p>
          </div>
          <div class="grid gap-3 md:grid-cols-3">
            <InfoItem label="任务编号" :value="task.task_code || task.id" />
            <InfoItem label="设备" :value="task.device_name || '未绑定设备'" />
            <InfoItem label="产品系列" :value="task.product_series || '-'" />
            <InfoItem label="故障类型" :value="labelOf(task.fault_type)" />
            <InfoItem label="告警代码" :value="task.alarm_code || '-'" />
            <InfoItem label="负责人" :value="task.assignee_name || task.assignee || '-'" />
          </div>
          <div class="flex flex-wrap gap-2">
            <StatusPill :value="task.priority" />
            <StatusPill :value="task.task_status || task.status" />
          </div>
        </div>
      </DataPanel>

      <DataPanel title="任务操作">
        <div class="space-y-3">
          <button v-if="canStart" class="scada-button primary w-full" type="button" @click="startTask">开始任务</button>
          <form v-if="canComplete" class="grid gap-3" @submit.prevent="completeTask">
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              完工总结
              <textarea v-model.trim="completeForm.completion_summary" class="scada-input min-h-20" required></textarea>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              根因判断
              <textarea v-model.trim="completeForm.root_cause" class="scada-input min-h-20" required></textarea>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              实际处理方案
              <textarea v-model.trim="completeForm.actual_solution" class="scada-input min-h-20" required></textarea>
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              使用部件
              <input v-model.trim="completeForm.used_parts" class="scada-input" placeholder="多个部件用逗号分隔；无更换可填“无”" />
            </label>
            <label class="grid gap-1 text-sm font-bold text-slate-200">
              安全复核结果
              <textarea v-model.trim="completeForm.safety_check_result" class="scada-input min-h-20" required></textarea>
            </label>
            <label class="flex items-center gap-2 text-sm font-bold text-slate-200">
              <input v-model="completeForm.follow_up_required" type="checkbox" class="h-4 w-4 accent-cyan-400" />
              需要后续跟进
            </label>
            <button class="scada-button primary" type="submit">完成任务</button>
          </form>
          <button v-if="canCancel" class="scada-button w-full" type="button" @click="cancelTask">取消任务</button>
          <EmptyState v-if="!canStart && !canComplete && !canCancel" :text="readonlyHint" />
        </div>
      </DataPanel>

      <DataPanel title="现场与完工图片" class="xl:col-span-2">
        <MediaEvidencePicker
          v-model="completionMediaIds"
          :title="canComplete ? '选择或上传完工图片' : '任务关联图片'"
          :device-id="task.device_id || ''"
          :manufacturer="task.manufacturer || ''"
          :product-series="task.product_series || ''"
          :fault-type="task.fault_type || ''"
          :alarm-code="task.alarm_code || ''"
          :task-id="task.id"
          :readonly="!canComplete"
        />
        <MediaEvidenceGallery v-if="detailMediaItems.length" class="mt-4" :items="detailMediaItems" />
      </DataPanel>

      <DataPanel v-if="showEditPanel" title="编辑任务" class="xl:col-span-2">
        <form class="grid gap-4 lg:grid-cols-2" @submit.prevent="saveEdit">
          <label class="grid gap-1 text-sm font-bold text-slate-200 lg:col-span-2">
            任务标题
            <input v-model.trim="editForm.title" class="scada-input" required />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            优先级
            <select v-model="editForm.priority" class="scada-input">
              <option v-for="item in priorityOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            故障类型
            <select v-model="editForm.fault_type" class="scada-input">
              <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            告警代码
            <input v-model.trim="editForm.alarm_code" class="scada-input" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            SOP 模板
            <select v-model="editForm.sop_template_id" class="scada-input">
              <option value="">不关联 SOP 模板</option>
              <option v-for="template in sopTemplates" :key="template.id" :value="template.id">{{ template.title }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200 lg:col-span-2">
            故障描述
            <textarea v-model.trim="editForm.fault_description" class="scada-input min-h-28"></textarea>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200 lg:col-span-2">
            备注
            <textarea v-model.trim="editForm.remark" class="scada-input min-h-20"></textarea>
          </label>
          <div class="flex flex-wrap gap-2 lg:col-span-2">
            <button class="scada-button primary" type="submit" :disabled="savingEdit">
              <Save :size="16" />
              {{ savingEdit ? '保存中' : '保存修改' }}
            </button>
            <button class="scada-button" type="button" @click="showEditPanel = false">取消</button>
          </div>
        </form>
      </DataPanel>

      <DataPanel v-if="showAssignPanel" title="重新分派任务" class="xl:col-span-2">
        <form class="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto]" @submit.prevent="saveAssign">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            负责人
            <select v-model="assignForm.assignee_id" class="scada-input" required>
              <option value="" disabled>请选择管理员、专家或工程师用户</option>
              <option v-for="user in assignableUsers" :key="user.id" :value="user.id">
                {{ user.display_name || user.username }} / {{ formatRoleLabel(user.role) }}
              </option>
            </select>
          </label>
          <div class="flex items-end gap-2">
            <button class="scada-button primary" type="submit" :disabled="savingAssign || !assignForm.assignee_id">
              <UserRoundCog :size="16" />
              {{ savingAssign ? '分派中' : '确认分派' }}
            </button>
            <button class="scada-button" type="button" @click="showAssignPanel = false">取消</button>
          </div>
        </form>
      </DataPanel>

      <DataPanel title="关联信息" class="xl:col-span-2">
        <div class="grid gap-3 md:grid-cols-3">
          <InfoItem v-for="item in relatedInfo" :key="item.label" :label="item.label" :value="item.value" />
        </div>
        <div v-if="task.suggested_steps?.length" class="mt-4 rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">建议步骤</h3>
          <ol class="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-slate-300">
            <li v-for="(step, index) in task.suggested_steps" :key="index">{{ step }}</li>
          </ol>
        </div>
      </DataPanel>
    </div>
    <EmptyState v-else text="未读取到任务详情" />
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { Pencil, RefreshCcw, Save, UserRoundCog } from '@lucide/vue'
import {
  assignWorkorderApi,
  cancelWorkorderApi,
  completeWorkorderApi,
  getAssignableUsersApi,
  getSopTemplatesApi,
  getWorkorderApi,
  startWorkorderApi,
  updateWorkorderApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import MediaEvidenceGallery from '@/components/MediaEvidenceGallery.vue'
import MediaEvidencePicker from '@/components/MediaEvidencePicker.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useUserStore } from '@/stores/user'
import { faultTypeOptions, priorityOptions } from '@/types'
import type { AssignableUser, MaintenanceTask, MediaContextItem, SOPTemplate } from '@/types'
import { formatRecordTypeLabel, formatRoleLabel } from '@/utils/display'

const InfoItem = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true }
  },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-md bg-white/[0.03] p-3' }, [
        h('div', { class: 'text-xs font-bold text-slate-400' }, props.label),
        h('div', { class: 'mt-1 break-words text-sm font-black text-white' }, props.value)
      ])
  }
})

const route = useRoute()
const userStore = useUserStore()
const detail = ref<Record<string, unknown> | null>(null)
const task = ref<MaintenanceTask | null>(null)
const sopTemplates = ref<SOPTemplate[]>([])
const assignableUsers = ref<AssignableUser[]>([])
const loading = ref(false)
const savingEdit = ref(false)
const savingAssign = ref(false)
const showEditPanel = ref(false)
const showAssignPanel = ref(false)
const error = ref('')
const completionMediaIds = ref<string[]>([])
const completeForm = reactive({
  completion_summary: '',
  root_cause: '',
  actual_solution: '',
  used_parts: '',
  safety_check_result: '',
  follow_up_required: false
})
const editForm = reactive({
  title: '',
  priority: 'medium',
  fault_type: 'unknown',
  alarm_code: '',
  fault_description: '',
  remark: '',
  sop_template_id: ''
})
const assignForm = reactive({ assignee_id: '' })

const status = computed(() => task.value?.task_status || task.value?.status || '')
const allowedTransitions = computed(() => (detail.value?.allowed_transitions as string[] | undefined) ?? [])
const isTerminal = computed(() => ['completed', 'cancelled'].includes(status.value))
const canWrite = computed(() => {
  if (!task.value) return false
  if (['admin', 'expert'].includes(userStore.role || '')) return true
  if (userStore.role !== 'engineer') return false
  return task.value.assignee_id === userStore.user?.id || task.value.created_by === userStore.user?.id
})
const canEdit = computed(() => canWrite.value && !isTerminal.value)
const canReassign = computed(
  () => ['admin', 'expert'].includes(userStore.role || '') && ['pending', 'assigned'].includes(status.value)
)
const canStart = computed(() => canWrite.value && allowedTransitions.value.includes('start'))
const canComplete = computed(() => canWrite.value && allowedTransitions.value.includes('complete'))
const canCancel = computed(() => canWrite.value && allowedTransitions.value.includes('cancel'))
const readonlyHint = computed(() =>
  userStore.role === 'viewer' ? '当前账号为只读角色，可查看任务但不能执行写操作。' : '当前状态没有可执行的任务流转操作。'
)
const relatedInfo = computed(() => {
  const current = task.value
  if (!current) return []
  return [
    { label: '创建人', value: current.created_by_name || '-' },
    {
      label: '来源类型',
      value: formatRecordTypeLabel((detail.value?.source_type as string) || current.source_type)
    },
    { label: '来源 trace_id', value: current.source_trace_id || current.diagnosis_trace_id || current.qa_trace_id || '-' },
    { label: 'SOP 模板', value: current.sop_template_id || '-' },
    { label: '备注', value: current.completion_notes || '-' },
    { label: '根因', value: current.root_cause || '-' },
    { label: '处理措施', value: current.repair_action || '-' },
    { label: '复检结果', value: current.verification_result || '-' },
    { label: '计划截止', value: formatTime(current.planned_end_at || current.due_date) },
    { label: '完成时间', value: formatTime(current.completed_at) }
  ]
})
const detailMediaItems = computed(
  () => ((detail.value?.media_items as MediaContextItem[] | undefined) ?? [])
)

async function loadDetail() {
  loading.value = true
  error.value = ''
  try {
    const data = await getWorkorderApi(String(route.params.id))
    detail.value = data
    task.value = (data.task || data) as MaintenanceTask
    completionMediaIds.value = detailMediaItems.value.map((item) => item.id)
    if (isTerminal.value) {
      showEditPanel.value = false
      showAssignPanel.value = false
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务详情读取失败'
    detail.value = null
    task.value = null
  } finally {
    loading.value = false
  }
}

async function openEdit() {
  if (!task.value || !canEdit.value) return
  editForm.title = task.value.title
  editForm.priority = task.value.priority
  editForm.fault_type = task.value.fault_type || 'unknown'
  editForm.alarm_code = task.value.alarm_code || ''
  editForm.fault_description = task.value.fault_description || ''
  editForm.remark = task.value.completion_notes || ''
  editForm.sop_template_id = task.value.sop_template_id || ''
  showAssignPanel.value = false
  showEditPanel.value = true
  if (!sopTemplates.value.length) {
    try {
      const result = await getSopTemplatesApi({ page: 1, page_size: 100, device_type: 'pv_inverter', status: 'active' })
      sopTemplates.value = result.items
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'SOP 模板读取失败'
    }
  }
}

async function saveEdit() {
  if (!task.value || !canEdit.value) return
  savingEdit.value = true
  error.value = ''
  try {
    await updateWorkorderApi(task.value.id, {
      title: editForm.title,
      priority: editForm.priority,
      fault_type: editForm.fault_type,
      alarm_code: editForm.alarm_code || null,
      fault_description: editForm.fault_description || null,
      remark: editForm.remark || null,
      sop_template_id: editForm.sop_template_id || null
    })
    toast('检修任务已更新')
    showEditPanel.value = false
    await loadDetail()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务更新失败'
  } finally {
    savingEdit.value = false
  }
}

async function openAssign() {
  if (!task.value || !canReassign.value) return
  showEditPanel.value = false
  showAssignPanel.value = true
  assignForm.assignee_id = task.value.assignee_id || ''
  try {
    assignableUsers.value = await getAssignableUsersApi()
  } catch (err) {
    assignableUsers.value = []
    error.value = err instanceof Error ? err.message : '可分派用户读取失败'
  }
}

async function saveAssign() {
  if (!task.value || !canReassign.value || !assignForm.assignee_id) return
  savingAssign.value = true
  error.value = ''
  try {
    await assignWorkorderApi(task.value.id, assignForm.assignee_id)
    toast('检修任务已重新分派')
    showAssignPanel.value = false
    await loadDetail()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务分派失败'
  } finally {
    savingAssign.value = false
  }
}

async function startTask() {
  await runAction(() => startWorkorderApi(String(route.params.id)), '任务已开始')
}

async function completeTask() {
  await runAction(
    () =>
      completeWorkorderApi(String(route.params.id), {
        root_cause: completeForm.root_cause,
        repair_action: completeForm.actual_solution,
        replaced_parts: completeForm.used_parts
          .split(/[，,]/)
          .map((item) => item.trim())
          .filter((item) => item && item !== '无'),
        verification_result: completeForm.safety_check_result,
        maintenance_record_remark: [
          completeForm.completion_summary,
          `后续跟进：${completeForm.follow_up_required ? '需要' : '不需要'}`
        ].join('\n'),
        media_ids: completionMediaIds.value
      }),
    '任务已完成'
  )
}

async function cancelTask() {
  await runAction(() => cancelWorkorderApi(String(route.params.id), '前端详情页取消任务'), '任务已取消')
}

async function runAction(fn: () => Promise<unknown>, message: string) {
  error.value = ''
  try {
    await fn()
    toast(message)
    await loadDetail()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务操作失败'
  }
}

function labelOf(value?: string | null) {
  return faultTypeOptions.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(loadDetail)
</script>
