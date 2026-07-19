export type MaintenanceWorkflowStage =
  | 'CASE_ANALYSIS'
  | 'EVIDENCE_REVIEW'
  | 'DIAGNOSIS_REVIEW'
  | 'SOP_DRAFT'
  | 'SOP_REVIEW'
  | 'TASK_DRAFT'
  | 'TASK_CREATED'
  | 'TASK_EXECUTION'
  | 'RESULT_VERIFICATION'
  | 'TASK_COMPLETED'
  | 'CORRECTION_REVIEW'
  | 'CLOSED'

export interface WorkflowAction {
  action: string
  allowed: boolean
  disabled_reason?: string | null
}

export interface WorkflowEvent {
  event_id: string
  workflow_id: string
  case_id: string
  task_id?: string | null
  actor_id: string
  actor_role: string
  event_type: string
  before: Record<string, unknown>
  after: Record<string, unknown>
  reason?: string | null
  created_at?: string | null
}

export interface WorkflowStep {
  step_id: string
  task_id: string
  sop_step_id: string
  sequence: number
  status: string
  result_summary?: string | null
  evidence_ids: string[]
  skip_reason?: string | null
  verification_status: string
  is_required: boolean
  is_safety_step: boolean
  prerequisites: string[]
}

export interface WorkflowExecutionRecord {
  record_id: string
  id: string
  task_id: string
  step_id?: string | null
  record_type: string
  content?: string | null
  media_ids: string[]
  measurements: Array<Record<string, unknown>>
  parts_replaced: string[]
  performed_by: string
  performed_at?: string | null
  safety_state: string
  result: Record<string, unknown>
  evidence_hash: string
  version: number
}

export interface MaintenanceWorkflow {
  workflow_id: string
  case_id: string
  device_id?: string | null
  diagnosis_id?: string | null
  approved_sop_id?: string | null
  formal_task_id?: string | null
  record_id?: string | null
  current_stage: MaintenanceWorkflowStage
  status: string
  blocking_reason?: string | null
  required_action?: string | null
  diagnosis_status: string
  diagnosis_version: number
  sop_version: number
  task_draft_version: number
  diagnosis_match_status: string
  correction_candidate_ids: string[]
  allowed_actions: WorkflowAction[]
  case?: Record<string, any> | null
  diagnosis?: Record<string, any> | null
  diagnosis_snapshot?: Record<string, any>
  sop_draft?: Record<string, any> | null
  approved_sop?: Record<string, any> | null
  task_draft?: Record<string, any> | null
  formal_task?: Record<string, any> | null
  steps?: WorkflowStep[]
  execution_records?: WorkflowExecutionRecord[]
  corrections?: Array<Record<string, any>>
  timeline?: WorkflowEvent[]
  created_at?: string | null
  updated_at?: string | null
}

export interface MaintenanceWorkflowPage {
  items: MaintenanceWorkflow[]
  total: number
  page: number
  page_size: number
}

export interface MaintenanceWorkflowStatus {
  status: string
  workflows: number
  active: number
  completed: number
  blocked: number
  audit_coverage: number
  duplicate_active_workflows: number
  duplicate_formal_tasks: number
  task25c_status: string
  qwen3_rerank_status: string
  full_reindex_executed: boolean
}

