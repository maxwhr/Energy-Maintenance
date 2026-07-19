<template>
  <PageFrame
    data-testid="maintenance-workflow-page"
    title="检修业务闭环"
    code="MAINTENANCE / WORKFLOW"
    description="将多模态案例、证据约束诊断、SOP 审核、正式任务、现场记录、完成验证与知识纠错串成可审计闭环。所有正式转换均需人工显式操作。"
  >
    <template #actions>
      <StatusPill :value="quality?.status || 'loading'" :label="quality?.status || '状态读取中'" />
      <button class="scada-button" type="button" :disabled="busy" @click="refreshAll">刷新</button>
    </template>

    <div v-if="error" data-testid="workflow-error" class="rounded border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">
      {{ error }}
    </div>

    <DataPanel title="业务边界" subtitle="Task 25C 与 R6 的未完成边界不会被本工作台隐藏。">
      <div class="grid gap-3 md:grid-cols-4">
        <Metric label="Task 25C" :value="quality?.task25c_status || '-'" />
        <Metric label="Qwen3 Rerank" :value="quality?.qwen3_rerank_status || '-'" />
        <Metric label="正式全量重建" :value="quality?.full_reindex_executed ? '已执行' : '未执行'" />
        <Metric label="审计覆盖率" :value="percent(quality?.audit_coverage)" />
      </div>
    </DataPanel>

    <div class="grid gap-4 2xl:grid-cols-[340px_minmax(0,1fr)]">
      <div class="space-y-4">
        <DataPanel title="创建 Workflow" subtitle="复用已持久化多模态案例；一个案例最多一个 active workflow。">
          <form class="grid gap-2" data-testid="workflow-create-form" @submit.prevent="createWorkflow">
            <input v-model.trim="createForm.case_id" class="scada-input" placeholder="case_id" :disabled="isViewer" />
            <input v-model.trim="createForm.device_id" class="scada-input" placeholder="device_id（可选）" :disabled="isViewer" />
            <input v-model.trim="createForm.reason" class="scada-input" placeholder="创建原因" :disabled="isViewer" />
            <button class="scada-button primary" type="submit" :disabled="isViewer || busy || !createForm.case_id">
              创建或返回已有 Workflow
            </button>
            <p v-if="isViewer" class="text-xs text-amber-100">viewer 只读，不能执行任何写操作。</p>
          </form>
        </DataPanel>

        <DataPanel title="Workflow 列表" :subtitle="`共 ${page.total} 条`">
          <div class="mb-3 grid grid-cols-2 gap-2">
            <select v-model="filters.status" class="scada-input" @change="loadWorkflows">
              <option value="">全部状态</option>
              <option v-for="value in workflowStatuses" :key="value" :value="value">{{ value }}</option>
            </select>
            <input v-model.trim="filters.device_id" class="scada-input" placeholder="设备 ID" @keyup.enter="loadWorkflows" />
          </div>
          <div data-testid="workflow-list" class="max-h-[620px] space-y-2 overflow-auto">
            <button
              v-for="item in page.items"
              :key="item.workflow_id"
              type="button"
              data-testid="workflow-list-item"
              class="w-full rounded border p-3 text-left"
              :class="workflow?.workflow_id === item.workflow_id ? 'border-cyan-300/60 bg-cyan-400/10' : 'border-slate-600/20 bg-black/20'"
              @click="selectWorkflow(item.workflow_id)"
            >
              <div class="flex items-center justify-between gap-2">
                <strong class="text-sm text-white">{{ item.case_id }}</strong>
                <StatusPill :value="item.status.toLowerCase()" :label="item.status" />
              </div>
              <div class="mt-2 text-xs text-cyan-100">{{ item.current_stage }}</div>
              <div class="mt-1 truncate text-[11px] text-slate-500">{{ item.workflow_id }}</div>
            </button>
            <EmptyState v-if="!page.items.length" text="暂无有权限查看的检修工作流" />
          </div>
        </DataPanel>
      </div>

      <div v-if="workflow" class="space-y-4">
        <DataPanel data-testid="workflow-stage-panel" title="当前阶段与阻塞状态">
          <div class="grid gap-3 md:grid-cols-4">
            <Metric label="当前阶段" :value="workflow.current_stage" />
            <Metric label="Workflow 状态" :value="workflow.status" />
            <Metric label="诊断状态" :value="workflow.diagnosis_status" />
            <Metric label="诊断匹配" :value="workflow.diagnosis_match_status" />
          </div>
          <div v-if="workflow.blocking_reason" class="mt-3 rounded border border-amber-300/30 bg-amber-400/10 p-3 text-sm text-amber-100">
            阻塞原因：{{ workflow.blocking_reason }}
          </div>
          <div v-if="workflow.required_action" class="mt-2 text-xs text-slate-300">下一步：{{ workflow.required_action }}</div>
          <ol class="mt-4 grid gap-2 md:grid-cols-4 xl:grid-cols-8">
            <li
              v-for="(stage, index) in stages"
              :key="stage.value"
              class="rounded border p-2 text-center text-[11px]"
              :class="stageTone(index)"
            >
              <div class="font-black">{{ index + 1 }}</div>
              <div>{{ stage.label }}</div>
            </li>
          </ol>
          <div class="mt-3 flex flex-wrap gap-2 text-xs">
            <span
              v-for="action in workflow.allowed_actions"
              :key="action.action"
              class="rounded border px-2 py-1"
              :class="action.allowed ? 'border-emerald-300/30 text-emerald-100' : 'border-slate-500/30 text-slate-500'"
              :title="action.disabled_reason || '允许'"
            >
              {{ action.action }}{{ action.allowed ? '' : `：${action.disabled_reason}` }}
            </span>
          </div>
        </DataPanel>

        <div class="grid gap-4 xl:grid-cols-2">
          <DataPanel title="案例、设备、媒体与证据">
            <JsonBlock :value="workflow.case || {}" empty="案例信息不可用" />
            <div class="mt-3 grid gap-2 md:grid-cols-2">
              <article v-for="item in caseEvidence" :key="item.evidence_id" class="rounded border border-slate-600/20 bg-black/20 p-3 text-xs">
                <div class="font-black text-cyan-100">{{ item.evidence_type }} / {{ item.observation_status }}</div>
                <p class="mt-1 text-slate-300">{{ item.observed_text || item.normalized_text || '-' }}</p>
                <div class="mt-1 text-[10px] text-slate-500">{{ item.evidence_id }}</div>
              </article>
            </div>
            <div v-if="caseConflicts.length" class="mt-3 rounded border border-red-300/30 bg-red-400/10 p-3 text-xs text-red-100">
              <div v-for="item in caseConflicts" :key="item.conflict_id">{{ item.severity }} / {{ item.conflict_type }} / {{ item.resolution_status }}</div>
            </div>
          </DataPanel>

          <DataPanel title="诊断草稿与人工确认" subtitle="模型只能生成 DRAFT；确认动作保留 actor/role/time/reason。">
            <div class="mb-3 flex flex-wrap gap-2">
              <ActionButton testid="diagnosis-draft" label="生成诊断草稿" action="diagnosis-draft" :workflow="workflow" :busy="busy" :viewer="isViewer" @run="runSimple('diagnosis-draft')" />
            </div>
            <JsonBlock :value="workflow.diagnosis_snapshot || workflow.diagnosis || {}" empty="尚无诊断草稿" />
            <form class="mt-3 grid gap-2" data-testid="diagnosis-confirm-form" @submit.prevent="confirmDiagnosis">
              <select v-model="diagnosisForm.action" class="scada-input" :disabled="isViewer">
                <option value="USER_CONFIRM">用户事实确认</option>
                <option value="ENGINEER_CONFIRM">工程诊断确认</option>
                <option value="EXPERT_REVIEW">高风险专家复核</option>
                <option value="REJECT">拒绝</option>
                <option value="REQUEST_REANALYSIS">请求重新分析</option>
              </select>
              <input v-model.trim="diagnosisForm.device_model" class="scada-input" placeholder="确认设备型号（确认操作需要）" :disabled="isViewer" />
              <input v-model.trim="diagnosisForm.selected_hypothesis_id" class="scada-input" placeholder="选择 hypothesis_id（可选）" :disabled="isViewer" />
              <textarea v-model.trim="diagnosisForm.comment" class="scada-input min-h-20" placeholder="确认/拒绝原因" :disabled="isViewer"></textarea>
              <ActionSubmit label="提交诊断确认" action="diagnosis-confirm" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
          </DataPanel>
        </div>

        <div class="grid gap-4 xl:grid-cols-2">
          <DataPanel title="SOP 草稿与审核" subtitle="Citation、安全要求和适用型号由服务端业务门校验。">
            <ActionButton testid="sop-draft" label="生成 SOP 草稿" action="sop-draft" :workflow="workflow" :busy="busy" :viewer="isViewer" @run="runSimple('sop-draft')" />
            <JsonBlock class="mt-3" :value="workflow.sop_draft || workflow.approved_sop || {}" empty="尚无 SOP 草稿" />
            <form class="mt-3 grid gap-2" @submit.prevent="reviewSop">
              <select v-model="sopForm.action" class="scada-input" :disabled="isViewer">
                <option value="APPROVE">批准当前版本</option>
                <option value="REJECT">拒绝</option>
                <option value="REQUEST_CHANGES">请求修改</option>
                <option value="CREATE_NEW_VERSION">创建新版本</option>
              </select>
              <textarea v-model.trim="sopForm.comment" class="scada-input min-h-20" placeholder="审核理由（必填）" :disabled="isViewer"></textarea>
              <ActionSubmit label="提交 SOP 审核" action="sop-review" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
          </DataPanel>

          <DataPanel title="Task Draft 与正式任务创建" subtitle="生成草稿不会自动创建或分配正式任务。">
            <div class="grid gap-2">
              <input v-model.trim="taskForm.title" class="scada-input" placeholder="任务标题（可选）" :disabled="isViewer" />
              <select v-model="taskForm.priority" class="scada-input" :disabled="isViewer">
                <option value="low">low</option><option value="medium">medium</option><option value="high">high</option><option value="urgent">urgent</option>
              </select>
              <label class="flex items-center gap-2 text-xs text-slate-300"><input v-model="taskForm.personal_preparation_confirmed" type="checkbox" :disabled="isViewer" />仅用于个人检修准备（仍为草稿）</label>
              <ActionButton testid="task-draft" label="生成 Task Draft" action="task-draft" :workflow="workflow" :busy="busy" :viewer="isViewer" @run="createTaskDraft" />
            </div>
            <JsonBlock class="mt-3" :value="workflow.task_draft || workflow.formal_task || {}" empty="尚无任务草稿" />
            <form class="mt-3 grid gap-2" data-testid="formal-task-form" @submit.prevent="createFormalTask">
              <input v-model.trim="taskForm.assignee_id" class="scada-input" placeholder="明确选择 assignee_id（可选）" :disabled="isViewer" />
              <textarea v-model.trim="taskForm.comment" class="scada-input min-h-20" placeholder="创建正式任务的人工确认理由" :disabled="isViewer"></textarea>
              <ActionSubmit label="显式创建正式任务" action="formal-task" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
          </DataPanel>
        </div>

        <DataPanel title="任务执行、步骤与现场记录" subtitle="记录不可覆盖；修正会生成新版本。图片复用现有 Media 服务。">
          <div class="mb-3 flex flex-wrap gap-2">
            <ActionButton testid="task-start" label="开始任务" action="task/start" :workflow="workflow" :busy="busy" :viewer="isViewer" @run="taskAction('start')" />
            <ActionButton label="暂停" action="task/pause" :workflow="workflow" :busy="busy" :viewer="isViewer" @run="taskAction('pause')" />
            <ActionButton label="恢复" action="task/resume" :workflow="workflow" :busy="busy" :viewer="isViewer" @run="taskAction('resume')" />
          </div>
          <div class="grid gap-3 xl:grid-cols-2">
            <div class="space-y-2">
              <article v-for="step in workflow.steps || []" :key="step.step_id" class="rounded border border-slate-600/20 bg-black/20 p-3">
                <div class="flex items-center justify-between gap-2"><strong class="text-sm text-white">{{ step.sequence }}. {{ step.sop_step_id }}</strong><StatusPill :value="step.status.toLowerCase()" :label="step.status" /></div>
                <div class="mt-2 grid gap-2 md:grid-cols-2">
                  <select v-model="stepInput(step.step_id).status" class="scada-input" :disabled="isViewer">
                    <option value="IN_PROGRESS">IN_PROGRESS</option><option value="COMPLETED">COMPLETED</option><option value="SKIPPED_WITH_REASON">SKIPPED_WITH_REASON</option><option value="BLOCKED">BLOCKED</option><option value="FAILED">FAILED</option>
                  </select>
                  <select v-model="stepInput(step.step_id).verification_status" class="scada-input" :disabled="isViewer">
                    <option value="PENDING">PENDING</option><option value="PASSED">PASSED</option><option value="FAILED">FAILED</option><option value="NOT_APPLICABLE">NOT_APPLICABLE</option>
                  </select>
                  <input v-model.trim="stepInput(step.step_id).result_summary" class="scada-input" placeholder="执行结果" :disabled="isViewer" />
                  <input v-model.trim="stepInput(step.step_id).skip_reason" class="scada-input" placeholder="跳过原因（跳过时必填）" :disabled="isViewer" />
                </div>
                <button class="scada-button mt-2" type="button" :disabled="isViewer || busy || !actionAllowed('task/steps')" :title="disabledReason('task/steps')" @click="updateStep(step.step_id)">保存步骤状态</button>
                <p v-if="!actionAllowed('task/steps')" class="mt-1 text-[11px] text-slate-500">{{ disabledReason('task/steps') }}</p>
              </article>
              <EmptyState v-if="!(workflow.steps || []).length" text="正式任务创建后显示 SOP 步骤" />
            </div>

            <form class="grid content-start gap-2" data-testid="task-record-form" @submit.prevent="addRecord">
              <select v-model="recordForm.record_type" class="scada-input" :disabled="isViewer">
                <option v-for="value in recordTypes" :key="value" :value="value">{{ value }}</option>
              </select>
              <textarea v-model.trim="recordForm.content" class="scada-input min-h-20" placeholder="现场记录/新发现/安全说明" :disabled="isViewer"></textarea>
              <input v-model.trim="recordForm.media_ids" class="scada-input" placeholder="已有 media_id，逗号分隔" :disabled="isViewer" />
              <div class="flex gap-2"><input type="file" accept="image/jpeg,image/png,image/webp" :disabled="isViewer" @change="selectExecutionFile" /><button class="scada-button" type="button" :disabled="isViewer || busy || !executionFile" @click="uploadExecutionImage">上传执行图片</button></div>
              <div class="grid grid-cols-3 gap-2"><input v-model.trim="recordForm.measurement_name" class="scada-input" placeholder="测量项" /><input v-model.trim="recordForm.measurement_value" class="scada-input" placeholder="数值" /><input v-model.trim="recordForm.measurement_unit" class="scada-input" placeholder="单位" /></div>
              <input v-model.trim="recordForm.parts_replaced" class="scada-input" placeholder="更换部件，逗号分隔" :disabled="isViewer" />
              <select v-model="recordForm.safety_state" class="scada-input" :disabled="isViewer"><option>NORMAL</option><option>WARNING</option><option>BLOCKED</option><option>RESOLVED</option></select>
              <ActionSubmit label="添加不可变执行记录" action="task/records" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
          </div>
          <div class="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            <article v-for="item in workflow.execution_records || []" :key="item.record_id" class="rounded border border-slate-600/20 bg-black/20 p-3 text-xs">
              <div class="flex justify-between"><strong class="text-cyan-100">{{ item.record_type }}</strong><span>v{{ item.version }}</span></div>
              <p class="mt-1 text-slate-300">{{ item.content || '-' }}</p>
              <div class="mt-1 break-all text-[10px] text-slate-500">{{ item.record_id }} / {{ item.evidence_hash }}</div>
            </article>
          </div>
        </DataPanel>

        <div class="grid gap-4 xl:grid-cols-2">
          <DataPanel title="完成验证与显式关闭" subtitle="验证成功或授权接受的部分成功才允许关闭。">
            <form class="grid gap-2" data-testid="task-verify-form" @submit.prevent="verifyTask">
              <select v-model="verifyForm.outcome" class="scada-input" :disabled="isViewer"><option>VERIFIED_SUCCESS</option><option>VERIFIED_PARTIAL</option><option>VERIFICATION_FAILED</option><option>NEEDS_REWORK</option></select>
              <textarea v-model.trim="verifyForm.verification_summary" class="scada-input min-h-20" placeholder="验证结论" :disabled="isViewer"></textarea>
              <label class="text-xs text-slate-300"><input v-model="verifyForm.accepted_partial" type="checkbox" /> 接受部分成功</label>
              <label class="text-xs text-slate-300"><input v-model="verifyForm.required_measurements_present" type="checkbox" /> 必需测量值已存在</label>
              <label class="text-xs text-slate-300"><input v-model="verifyForm.required_media_present" type="checkbox" /> 必需图片已存在</label>
              <ActionSubmit label="提交完成验证" action="task/verify" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
            <form class="mt-4 grid gap-2" data-testid="task-complete-form" @submit.prevent="completeTask">
              <textarea v-model.trim="completeForm.actual_fault_cause" class="scada-input min-h-20" placeholder="实际故障原因" :disabled="isViewer"></textarea>
              <textarea v-model.trim="completeForm.actual_actions" class="scada-input min-h-20" placeholder="实际动作，每行一项" :disabled="isViewer"></textarea>
              <input v-model.trim="completeForm.replaced_parts" class="scada-input" placeholder="更换部件，逗号分隔" />
              <input v-model.trim="completeForm.final_device_status" class="scada-input" placeholder="最终设备状态" />
              <select v-model="completeForm.diagnosis_match_status" class="scada-input"><option>MATCHED</option><option>PARTIALLY_MATCHED</option><option>MISMATCHED</option><option>UNDETERMINED</option></select>
              <textarea v-model.trim="completeForm.comment" class="scada-input min-h-20" placeholder="人工关闭理由" :disabled="isViewer"></textarea>
              <ActionSubmit label="显式完成正式任务" action="task/complete" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
          </DataPanel>

          <DataPanel title="知识纠错候选" subtitle="只创建 DRAFT，不自动审批、写知识或重建索引。">
            <form class="grid gap-2" data-testid="correction-form" @submit.prevent="createCorrection">
              <select v-model="correctionForm.candidate_type" class="scada-input" :disabled="isViewer"><option v-for="value in correctionTypes" :key="value">{{ value }}</option></select>
              <textarea v-model.trim="correctionForm.proposed_change" class="scada-input min-h-20" placeholder="建议变更内容" :disabled="isViewer"></textarea>
              <textarea v-model.trim="correctionForm.reason" class="scada-input min-h-20" placeholder="原因" :disabled="isViewer"></textarea>
              <input v-model.trim="correctionForm.evidence_ids" class="scada-input" placeholder="workflow 证据/执行记录 ID，逗号分隔" :disabled="isViewer" />
              <ActionSubmit label="创建 Correction Draft" action="correction-candidate" :workflow="workflow" :busy="busy" :viewer="isViewer" />
            </form>
            <JsonBlock class="mt-3" :value="workflow.corrections || []" empty="尚无纠错候选" />
          </DataPanel>
        </div>

        <DataPanel data-testid="workflow-timeline" title="完整审计时间线" subtitle="每次转换记录 before/after、actor、role、time 与 reason。">
          <ol class="space-y-2 border-l border-cyan-300/30 pl-4">
            <li v-for="item in workflow.timeline || []" :key="item.event_id" class="relative rounded bg-black/20 p-3 text-sm">
              <span class="absolute -left-[21px] top-4 h-2 w-2 rounded-full bg-cyan-300"></span>
              <div class="flex flex-wrap items-center justify-between gap-2"><strong class="text-white">{{ item.event_type }}</strong><span class="text-xs text-slate-500">{{ formatTime(item.created_at) }}</span></div>
              <div class="mt-1 text-xs text-slate-300">{{ item.actor_role }} / {{ item.actor_id }} / {{ item.reason || '-' }}</div>
            </li>
          </ol>
          <EmptyState v-if="!(workflow.timeline || []).length" text="暂无时间线事件" />
        </DataPanel>
      </div>

      <DataPanel v-else title="请选择 Workflow"><EmptyState text="从左侧选择工作流，或由 engineer/admin 创建。" /></DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import {
  createMaintenanceWorkflow,
  getMaintenanceWorkflow,
  getMaintenanceWorkflows,
  getMaintenanceWorkflowStatus,
  getMultimodalCaseEvidence,
  postWorkflowAction,
  updateWorkflowStep,
  uploadMediaApi
} from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { useUserStore } from '@/stores/user'
import type { MaintenanceWorkflow, MaintenanceWorkflowPage, MaintenanceWorkflowStatus } from '@/types/maintenanceWorkflow'

const Metric = defineComponent({ props: { label: String, value: [String, Number] }, setup: (props) => () => h('div', { class: 'rounded border border-slate-600/20 bg-black/20 p-3' }, [h('div', { class: 'text-[11px] font-bold text-slate-400' }, props.label), h('div', { class: 'mt-1 break-words text-sm font-black text-white' }, String(props.value ?? '-'))]) })
const JsonBlock = defineComponent({ props: { value: { type: [Object, Array], required: true }, empty: String }, setup: (props) => () => Object.keys(props.value as object).length ? h('pre', { class: 'max-h-80 overflow-auto whitespace-pre-wrap break-words rounded bg-black/20 p-3 text-xs text-slate-200' }, JSON.stringify(props.value, null, 2)) : h('div', { class: 'rounded border border-dashed border-slate-600/30 p-4 text-center text-xs text-slate-500' }, props.empty || '暂无数据') })
const ActionButton = defineComponent({ props: { label: String, action: String, workflow: { type: Object as () => MaintenanceWorkflow, required: true }, busy: Boolean, viewer: Boolean, testid: String }, emits: ['run'], setup: (props, { emit }) => { const found = computed(() => props.workflow.allowed_actions.find((item) => item.action === props.action)); const reason = computed(() => props.viewer ? 'viewer 无写权限' : found.value?.disabled_reason || (!found.value?.allowed ? `当前阶段 ${props.workflow.current_stage} 不允许此操作` : '')); return () => h('div', [h('button', { class: 'scada-button', type: 'button', 'data-testid': props.testid, disabled: props.viewer || props.busy || !found.value?.allowed, title: reason.value, onClick: () => emit('run') }, props.label), reason.value ? h('div', { class: 'mt-1 text-[11px] text-slate-500' }, reason.value) : null]) } })
const ActionSubmit = defineComponent({ props: { label: String, action: String, workflow: { type: Object as () => MaintenanceWorkflow, required: true }, busy: Boolean, viewer: Boolean }, setup: (props) => { const found = computed(() => props.workflow.allowed_actions.find((item) => item.action === props.action)); const reason = computed(() => props.viewer ? 'viewer 无写权限' : found.value?.disabled_reason || (!found.value?.allowed ? `当前阶段 ${props.workflow.current_stage} 不允许此操作` : '')); return () => h('div', [h('button', { class: 'scada-button primary', type: 'submit', disabled: props.viewer || props.busy || !found.value?.allowed, title: reason.value }, props.label), reason.value ? h('div', { class: 'mt-1 text-[11px] text-slate-500' }, reason.value) : null]) } })

const userStore = useUserStore()
const isViewer = computed(() => userStore.role === 'viewer')
const busy = ref(false)
const error = ref('')
const quality = ref<MaintenanceWorkflowStatus | null>(null)
const workflow = ref<MaintenanceWorkflow | null>(null)
const page = reactive<MaintenanceWorkflowPage>({ items: [], total: 0, page: 1, page_size: 50 })
const caseEvidence = ref<Record<string, any>[]>([])
const caseConflicts = ref<Record<string, any>[]>([])
const executionFile = ref<File | null>(null)
const stepForms = reactive<Record<string, { status: string; result_summary: string; skip_reason: string; verification_status: string }>>({})
const filters = reactive({ status: '', device_id: '' })
const createForm = reactive({ case_id: '', device_id: '', reason: '创建检修业务闭环' })
const diagnosisForm = reactive({ action: 'ENGINEER_CONFIRM', device_model: '', selected_hypothesis_id: '', comment: '' })
const sopForm = reactive({ action: 'APPROVE', comment: '' })
const taskForm = reactive({ title: '', priority: 'medium', personal_preparation_confirmed: false, assignee_id: '', comment: '' })
const recordForm = reactive({ record_type: 'NEW_FINDING', content: '', media_ids: '', measurement_name: '', measurement_value: '', measurement_unit: '', parts_replaced: '', safety_state: 'NORMAL' })
const verifyForm = reactive({ outcome: 'VERIFIED_SUCCESS', verification_summary: '', accepted_partial: false, required_measurements_present: false, required_media_present: false })
const completeForm = reactive({ actual_fault_cause: '', actual_actions: '', replaced_parts: '', final_device_status: '', diagnosis_match_status: 'UNDETERMINED', comment: '' })
const correctionForm = reactive({ candidate_type: 'ACTUAL_FAULT_MISMATCH', proposed_change: '', reason: '', evidence_ids: '' })

const workflowStatuses = ['ACTIVE', 'WAITING_USER', 'WAITING_ENGINEER', 'WAITING_EXPERT', 'BLOCKED', 'COMPLETED', 'CANCELLED', 'FAILED']
const recordTypes = ['STEP_RESULT', 'MEASUREMENT', 'PHOTO', 'PART_REPLACEMENT', 'SAFETY_EVENT', 'NEW_FINDING', 'EXPERT_ASSISTANCE']
const correctionTypes = ['ACTUAL_FAULT_MISMATCH', 'SOP_INCOMPLETE', 'MANUAL_AMBIGUITY', 'MODEL_VARIANT', 'ALARM_ALIAS', 'ACTION_MISMATCH', 'CITATION_LOCATOR_ERROR', 'OCR_VISUAL_FEEDBACK']
const stages = [
  { value: 'CASE_ANALYSIS', label: '案例' }, { value: 'EVIDENCE_REVIEW', label: '证据' }, { value: 'DIAGNOSIS_REVIEW', label: '诊断' }, { value: 'SOP_DRAFT', label: 'SOP 草稿' },
  { value: 'SOP_REVIEW', label: 'SOP 审核' }, { value: 'TASK_DRAFT', label: '任务草稿' }, { value: 'TASK_CREATED', label: '正式任务' }, { value: 'TASK_EXECUTION', label: '执行' },
  { value: 'RESULT_VERIFICATION', label: '验证' }, { value: 'TASK_COMPLETED', label: '完成' }, { value: 'CORRECTION_REVIEW', label: '纠错' }, { value: 'CLOSED', label: '关闭' }
]

const idempotency = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
const csv = (value: string) => value.split(',').map((item) => item.trim()).filter(Boolean)
const lines = (value: string) => value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean)
const percent = (value?: number) => `${Math.round((value || 0) * 100)}%`
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString() : '-'
const toast = (message: string) => window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
const actionAllowed = (action: string) => !!workflow.value?.allowed_actions.find((item) => item.action === action)?.allowed
const disabledReason = (action: string) => workflow.value?.allowed_actions.find((item) => item.action === action)?.disabled_reason || `当前阶段 ${workflow.value?.current_stage || '-'} 不允许此操作`
const stageTone = (index: number) => { const current = stages.findIndex((item) => item.value === workflow.value?.current_stage); return index === current ? 'border-cyan-300 bg-cyan-400/15 text-cyan-100' : index < current ? 'border-emerald-300/30 text-emerald-200' : 'border-slate-600/30 text-slate-500' }
const stepInput = (id: string) => stepForms[id] || (stepForms[id] = { status: 'IN_PROGRESS', result_summary: '', skip_reason: '', verification_status: 'PENDING' })

async function guarded(action: () => Promise<void>, success: string) { busy.value = true; error.value = ''; try { await action(); toast(success) } catch (err) { error.value = err instanceof Error ? err.message : '操作失败' } finally { busy.value = false } }
async function loadWorkflows() { const result = await getMaintenanceWorkflows({ page: 1, page_size: 50, status: filters.status || undefined, device_id: filters.device_id || undefined }); Object.assign(page, result) }
async function loadQuality() { quality.value = await getMaintenanceWorkflowStatus() }
async function selectWorkflow(id: string) { await guarded(async () => { workflow.value = await getMaintenanceWorkflow(id); const evidence = await getMultimodalCaseEvidence(workflow.value.case_id); caseEvidence.value = evidence.items; caseConflicts.value = evidence.conflicts || [] }, '工作流已刷新') }
async function refreshAll() { await guarded(async () => { await Promise.all([loadWorkflows(), loadQuality()]); if (workflow.value) await selectWorkflow(workflow.value.workflow_id) }, '数据已刷新') }
async function refreshSelected() { if (workflow.value) workflow.value = await getMaintenanceWorkflow(workflow.value.workflow_id); await Promise.all([loadWorkflows(), loadQuality()]) }
async function createWorkflow() { await guarded(async () => { const result = await createMaintenanceWorkflow({ case_id: createForm.case_id, device_id: createForm.device_id || null, reason: createForm.reason || null, idempotency_key: idempotency('workflow') }); workflow.value = result; await refreshSelected() }, 'Workflow 已创建或复用') }
async function runSimple(action: string) { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, action, { idempotency_key: idempotency(action), reason: `工作台执行 ${action}` }); await refreshSelected() }, `${action} 已提交`) }
async function confirmDiagnosis() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'diagnosis-confirm', { idempotency_key: idempotency('diagnosis-confirm'), action: diagnosisForm.action, confirmed_fields: diagnosisForm.device_model ? { device_model: diagnosisForm.device_model } : {}, rejected_fields: [], selected_hypothesis_id: diagnosisForm.selected_hypothesis_id || null, comment: diagnosisForm.comment || null }); await refreshSelected() }, '诊断确认已记录') }
async function reviewSop() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'sop-review', { idempotency_key: idempotency('sop-review'), action: sopForm.action, comment: sopForm.comment }); await refreshSelected() }, 'SOP 审核已记录') }
async function createTaskDraft() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'task-draft', { idempotency_key: idempotency('task-draft'), title: taskForm.title || null, priority: taskForm.priority, assignee_role: 'engineer', personal_preparation_confirmed: taskForm.personal_preparation_confirmed, comment: taskForm.comment || null }); await refreshSelected() }, 'Task Draft 已生成') }
async function createFormalTask() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'formal-task', { idempotency_key: idempotency('formal-task'), assignee_id: taskForm.assignee_id || null, comment: taskForm.comment }); await refreshSelected() }, '正式任务已显式创建') }
async function taskAction(action: string) { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, `task/${action}`, { idempotency_key: idempotency(`task-${action}`), reason: `${action} by workflow workbench` }); await refreshSelected() }, `任务 ${action} 已记录`) }
function selectExecutionFile(event: Event) { executionFile.value = (event.target as HTMLInputElement).files?.[0] || null }
async function uploadExecutionImage() { if (!workflow.value || !executionFile.value) return; await guarded(async () => { const form = new FormData(); form.append('file', executionFile.value!); form.append('media_type', 'maintenance_result'); form.append('device_type', 'pv_inverter'); if (workflow.value?.device_id) form.append('device_id', workflow.value.device_id); if (workflow.value?.formal_task_id) form.append('task_id', workflow.value.formal_task_id); const result = await uploadMediaApi(form); recordForm.media_ids = [...csv(recordForm.media_ids), result.media_id].join(','); recordForm.record_type = 'PHOTO'; executionFile.value = null }, '执行图片已上传，请提交 PHOTO 记录') }
async function addRecord() { if (!workflow.value) return; const measurements = recordForm.measurement_name && recordForm.measurement_unit ? [{ name: recordForm.measurement_name, value: recordForm.measurement_value, unit: recordForm.measurement_unit }] : []; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'task/records', { idempotency_key: idempotency('task-record'), record_type: recordForm.record_type, content: recordForm.content || null, media_ids: csv(recordForm.media_ids), measurements, parts_replaced: csv(recordForm.parts_replaced), safety_state: recordForm.safety_state, result: {} }); await refreshSelected() }, '执行记录已保存') }
async function updateStep(stepId: string) { if (!workflow.value) return; const form = stepInput(stepId); await guarded(async () => { await updateWorkflowStep(workflow.value!.workflow_id, stepId, { idempotency_key: idempotency(`step-${stepId}`), status: form.status, result_summary: form.result_summary || null, evidence_ids: [], skip_reason: form.skip_reason || null, verification_status: form.verification_status }); await refreshSelected() }, '步骤状态已保存') }
async function verifyTask() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'task/verify', { idempotency_key: idempotency('task-verify'), ...verifyForm }); await refreshSelected() }, '完成验证已提交') }
async function completeTask() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'task/complete', { idempotency_key: idempotency('task-complete'), comment: completeForm.comment, actual_fault_cause: completeForm.actual_fault_cause, actual_actions: lines(completeForm.actual_actions), replaced_parts: csv(completeForm.replaced_parts), final_device_status: completeForm.final_device_status, diagnosis_match_status: completeForm.diagnosis_match_status, user_feedback: null }); await refreshSelected() }, '正式任务已完成并回写案例') }
async function createCorrection() { if (!workflow.value) return; await guarded(async () => { await postWorkflowAction(workflow.value!.workflow_id, 'correction-candidate', { idempotency_key: idempotency('correction'), candidate_type: correctionForm.candidate_type, proposed_change: { proposal: correctionForm.proposed_change }, reason: correctionForm.reason, evidence_ids: csv(correctionForm.evidence_ids), source_document_ids: [], source_chunk_ids: [], semantic_unit_ids: [] }); await refreshSelected() }, 'Correction Draft 已创建，等待人工审核') }

onMounted(() => refreshAll())
</script>
