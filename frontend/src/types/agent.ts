export interface AgentDefinition {
  id: string
  agent_code: string
  agent_name: string
  agent_type: string
  description?: string | null
  enabled: boolean
  default_model_provider?: string | null
  default_model_name?: string | null
  tool_policy_json?: Record<string, unknown> | null
  safety_policy_json?: Record<string, unknown> | null
  metadata_json?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface AgentTool {
  id: string
  tool_name: string
  tool_display_name: string
  tool_type: string
  description?: string | null
  enabled: boolean
  requires_approval: boolean
  allowed_roles_json?: string[] | null
  input_schema_json?: Record<string, unknown> | null
  output_schema_json?: Record<string, unknown> | null
  risk_level?: string | null
  metadata_json?: AgentToolMetadata | null
  created_at: string
  updated_at: string
}

export interface AgentToolMetadata {
  external_api_route_code?: string
  provider?: string
  default_provider?: string
  external_provider_required?: boolean
  requires_external_config?: boolean
  external_api_called_by_default?: boolean
  [key: string]: unknown
}

export interface AgentRunCreatePayload {
  agent_code: string
  input_text?: string | null
  device_id?: string | null
  input_media_ids?: string[]
  media_ids?: string[]
  context?: Record<string, unknown>
  tool_names?: string[]
  tools?: string[]
  tool_inputs?: Record<string, Record<string, unknown>>
  requires_approval?: boolean
  dry_run?: boolean
  mock_run?: boolean
}

export interface AgentRun {
  id: string
  run_id: string
  agent_code: string
  user_id?: string | null
  device_id?: string | null
  status: string
  input_text?: string | null
  input_media_ids_json?: string[] | null
  context_json?: Record<string, unknown> | null
  provider?: string | null
  model_name?: string | null
  final_answer?: string | null
  confidence?: number | string | null
  requires_human_approval: boolean
  approval_status?: string | null
  error_code?: string | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at: string
  updated_at: string
}

export interface AgentStep {
  id: string
  run_id: string
  step_index: number
  step_type: string
  step_name: string
  status: string
  input_json?: Record<string, unknown> | null
  output_json?: Record<string, unknown> | null
  reasoning_summary?: string | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_at: string
}

export interface AgentToolCall {
  id: string
  run_id: string
  step_id?: string | null
  tool_name: string
  tool_version?: string | null
  status: string
  input_json?: Record<string, unknown> | null
  output_json?: Record<string, unknown> | null
  latency_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
}

export interface AgentApproval {
  id: string
  run_id: string
  approval_type: string
  requested_action: string
  payload_json?: Record<string, unknown> | null
  status: string
  requested_by?: string | null
  reviewed_by?: string | null
  review_comment?: string | null
  created_at: string
  reviewed_at?: string | null
}

export interface AgentArtifact {
  id: string
  run_id: string
  artifact_type: string
  title?: string | null
  content_text?: string | null
  content_json?: Record<string, unknown> | null
  source_type?: string | null
  source_id?: string | null
  created_at: string
}

export interface AgentEventLog {
  id: string
  run_id?: string | null
  event_type: string
  event_message?: string | null
  payload_json?: Record<string, unknown> | null
  created_by?: string | null
  created_at: string
}

export type AgentConversionTargetType =
  | 'knowledge_contribution'
  | 'sop_template'
  | 'maintenance_task'
  | 'kg_candidate'

export interface AgentArtifactConversionRequest {
  target_type: AgentConversionTargetType
  approval_id?: string | null
  override_warnings?: boolean
  comment?: string | null
}

export interface AgentArtifactConversionResult {
  id?: string | null
  conversion_trace_id: string
  source_artifact_id: string
  source_artifact_type: string
  source_agent_run_id: string
  approval_id?: string | null
  target_type: AgentConversionTargetType
  target_id?: string | null
  target_table?: string | null
  status: string
  conversion_status?: string | null
  warnings: string[]
  created_records: Record<string, unknown>
  message: string
  result_summary?: Record<string, unknown>
  metadata?: Record<string, unknown>
  already_converted?: boolean
  can_convert?: boolean
  blocked_reason?: string | null
  converted_by?: string | null
  requested_by?: string | null
  approved_by?: string | null
  voided_by?: string | null
  created_at?: string | null
  started_at?: string | null
  completed_at?: string | null
  failed_at?: string | null
  voided_at?: string | null
  converted_at?: string | null
  error_message?: string | null
}

export interface AgentArtifactConversionStatus {
  source_artifact_id: string
  source_artifact_type: string
  source_agent_run_id: string
  allowed_target_types: AgentConversionTargetType[]
  approval_status?: string | null
  approval_id?: string | null
  conversions: AgentArtifactConversionResult[]
  converted_targets: Partial<Record<AgentConversionTargetType, AgentArtifactConversionResult>>
  can_convert: boolean
  already_converted?: boolean
  blocked_reason?: string | null
  message?: string | null
}

export interface AgentRunDetail {
  run: AgentRun
  steps: AgentStep[]
  tool_calls: AgentToolCall[]
  approvals: AgentApproval[]
  artifacts: AgentArtifact[]
}

export interface AgentRunTimeline extends AgentRunDetail {
  events: AgentEventLog[]
  event_total?: number
}

export interface AgentToolExecutePayload {
  tool_name: string
  input?: Record<string, unknown>
  dry_run?: boolean
}

export interface AgentToolExecuteResult {
  tool_name: string
  status: string
  summary: string
  data: Record<string, unknown>
  evidence: Record<string, unknown>[]
  requires_approval: boolean
  blocked_reason?: string | null
  error_code?: string | null
  error_message?: string | null
}

export interface AgentPage<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}
