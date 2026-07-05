export type UserRole = 'admin' | 'expert' | 'engineer' | 'viewer'

export interface ApiResponse<T = unknown> {
  code: number
  message?: string
  msg?: string
  data: T
}

export * from './externalApi'
export * from './multimodal'

export interface PageResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface UserInfo {
  id: string
  username: string
  displayName: string
  role: UserRole
  roles: UserRole[]
  status: string
}

export interface BackendUser {
  id: string
  username: string
  display_name?: string | null
  role: UserRole | string
  status: string
  is_active?: boolean
  created_at?: string
  updated_at?: string
}

export interface LoginResult {
  token: string
  accessToken: string
  tokenType: string
  expiresIn: number
  user: UserInfo
}

export interface DeviceItem {
  id: string
  device_code?: string | null
  device_name: string
  manufacturer: string
  product_series?: string | null
  model?: string | null
  device_type: string
  station_name?: string | null
  location?: string | null
  commissioning_date?: string | null
  status: string
  last_fault_at?: string | null
  last_maintenance_at?: string | null
  fault_count: number
  maintenance_count: number
  description?: string | null
  created_at: string
  updated_at: string
}

export interface DeviceStatistics {
  total_devices?: number
  normal_devices?: number
  fault_devices?: number
  maintenance_devices?: number
  offline_devices?: number
  retired_devices?: number
  huawei_devices?: number
  sungrow_devices?: number
  recent_maintenance_records?: number
  [key: string]: unknown
}

export interface KnowledgeDocument {
  id: string
  title: string
  manufacturer: string
  product_series?: string | null
  model?: string | null
  device_type: string
  document_type: string
  source?: string | null
  source_type?: string | null
  file_name?: string | null
  original_file_name?: string | null
  file_size?: number | null
  file_ext?: string | null
  page_count?: number | null
  parse_status: string
  parser_name?: string | null
  chunk_count: number
  summary?: string | null
  error_message?: string | null
  review_status?: string
  status: string
  created_at: string
  updated_at: string
  vector_index_status?: DocumentVectorIndexStatus
}

export interface KnowledgeChunk {
  id: string
  document_id: string
  manufacturer: string
  product_series?: string | null
  device_type: string
  document_type: string
  chunk_index: number
  content: string
  section_title?: string | null
  char_count: number
  page_number?: number | null
  embedding_status: string
  status: string
  created_at: string
  updated_at: string
  vector_indexes?: ChunkVectorIndex[]
}

export interface KnowledgeUploadResult {
  document_id: string
  title: string
  status: string
  parse_status: string
  review_status?: string
  chunk_count: number
  file_name?: string | null
  original_file_name?: string | null
  warnings?: string[]
}

export interface KnowledgeContribution {
  id: string
  title: string
  content: string
  content_preview?: string | null
  contribution_type: string
  manufacturer?: string | null
  product_series?: string | null
  device_type: string
  device_id?: string | null
  device_name?: string | null
  source_type?: string | null
  source_trace_id?: string | null
  submitted_by?: string | null
  submitted_by_name?: string | null
  review_status: string
  review_comment?: string | null
  approved_document_id?: string | null
  approved_document_title?: string | null
  metadata_json?: Record<string, unknown>
  fault_type?: string | null
  alarm_code?: string | null
  symptom_description?: string | null
  diagnosis_process?: string | null
  root_cause?: string | null
  solution?: string | null
  tools_used?: string[]
  parts_used?: string[]
  safety_notes?: string[]
  media_ids?: string[]
  related_diagnosis_trace_id?: string | null
  related_task_id?: string | null
  qa_trace_id?: string | null
  review_records?: Record<string, unknown>[]
  created_at: string
  updated_at: string
}

export interface KnowledgeContributionPayload {
  title: string
  content?: string
  contribution_type: string
  manufacturer?: string
  product_series?: string
  device_type: string
  device_id?: string | null
  source_trace_id?: string | null
  fault_type?: string | null
  alarm_code?: string | null
  symptom_description?: string | null
  diagnosis_process?: string | null
  root_cause?: string | null
  solution?: string | null
  tools_used?: string[]
  parts_used?: string[]
  safety_notes?: string[]
  media_ids?: string[]
  related_diagnosis_trace_id?: string | null
  related_task_id?: string | null
  qa_trace_id?: string | null
  metadata_json?: Record<string, unknown>
}

export interface RetrievalReference {
  document_id?: string
  document_title?: string
  chunk_id?: string
  chunk_index?: number
  page_number?: number | null
  section_title?: string | null
  quote?: string
  manufacturer?: string | null
  product_series?: string | null
  device_type?: string | null
  document_type?: string | null
  source?: string | null
  score?: number
}

export interface RetrievedChunk {
  chunk_id: string
  document_id: string
  document_title: string
  chunk_index: number
  section_title?: string | null
  page_number?: number | null
  content: string
  score: number
  manufacturer: string
  product_series?: string | null
  device_type: string
  document_type: string
  source?: string | null
  created_at?: string
  keyword_score?: number | null
  vector_score?: number | null
  hybrid_score?: number | null
  retrieval_source?: 'keyword' | 'vector' | 'hybrid'
  vector_backend?: string | null
}

export interface RetrievalResponse {
  trace_id: string
  question: string
  answer: string
  suggested_steps: string[]
  safety_notes: string[]
  references: RetrievalReference[]
  retrieved_chunks: RetrievedChunk[]
  related_history?: Record<string, unknown>[]
  media_items: MediaContextItem[]
  media_notice?: string | null
  ocr_context?: OCRContextItem[]
  kg_context?: KGBusinessContext
  kg_nodes?: KGNode[]
  kg_edges?: KGEdge[]
  kg_evidence?: KGEvidence[]
  kg_paths?: KGPathItem[]
  confidence: number
  model_provider: string
  model_name: string
  model_enhanced: boolean
  model_call_trace_id?: string | null
  retrieval_mode?: string
  vector_enabled?: boolean
  vector_available?: boolean
  hybrid_used?: boolean
  vector_fallback_used?: boolean
  fallback_used?: boolean
  vector_backend?: string
  embedding_provider?: string | null
  embedding_model?: string | null
  retrieval_diagnostics?: Record<string, unknown>
}

export interface VectorSearchStatus {
  vector_search_enabled: boolean
  vector_backend: string
  dashvector_enabled: boolean
  dashvector_configured: boolean
  dashvector_collection: string
  dashvector_namespace?: string | null
  dashvector_dimension: number
  embedding_enabled: boolean
  embedding_configured: boolean
  embedding_provider: string
  embedding_model?: string | null
  embedding_dimension: number
  deterministic_test_enabled: boolean
  fake_adapter_available: boolean
  real_adapter_available: boolean
  status: string
  blocked_reasons: string[]
  warnings: string[]
}

export interface VectorIndexRun {
  id: string
  run_type: string
  target_type: string
  target_id?: string | null
  vector_backend: string
  collection_name: string
  namespace?: string | null
  embedding_model: string
  embedding_provider: string
  status: string
  total_count: number
  succeeded_count: number
  failed_count: number
  skipped_count: number
  started_at?: string | null
  finished_at?: string | null
  error_message?: string | null
  metadata_json?: Record<string, unknown> | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface ChunkVectorIndex {
  id: string
  chunk_id: string
  document_id?: string | null
  vector_backend: string
  collection_name: string
  namespace?: string | null
  vector_id: string
  embedding_model: string
  embedding_provider: string
  embedding_dim: number
  content_hash: string
  index_status: string
  last_indexed_at?: string | null
  error_message?: string | null
  metadata_json?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface DocumentVectorIndexStatus {
  document_id: string
  chunk_count: number
  indexed_count: number
  stale_count: number
  failed_count: number
  indexes: ChunkVectorIndex[]
}

export interface VectorIndexJobResult {
  run: VectorIndexRun
  processed: number
  succeeded: number
  skipped: number
  failed: number
  vector_backend: string
  embedding_provider: string
  embedding_model: string
  embedding_dimension: number
  warnings: string[]
}

export interface VectorTestQueryResult {
  vector_backend: string
  embedding_provider: string
  embedding_model: string
  embedding_dimension: number
  vector_available: boolean
  hits: Array<Record<string, unknown>>
  warnings: string[]
}

export interface DiagnosisResponse {
  trace_id: string
  device_id?: string | null
  fault_type: string
  alarm_code?: string | null
  diagnosis_summary: string
  possible_causes: string[]
  inspection_steps: string[]
  recommended_actions: string[]
  safety_notes: string[]
  references: RetrievalReference[]
  related_history: Record<string, unknown>[]
  media_ids?: string[]
  media_items: MediaContextItem[]
  media_notice?: string | null
  ocr_context?: OCRContextItem[]
  kg_context?: KGBusinessContext
  kg_related_causes?: KGBusinessNode[]
  kg_inspection_items?: KGBusinessNode[]
  kg_recommended_actions?: KGBusinessNode[]
  kg_safety_risks?: KGBusinessNode[]
  kg_evidence?: KGEvidence[]
  is_recurrent: boolean
  confidence: number
  model_provider: string
  model_name: string
  model_enhanced: boolean
  model_call_trace_id?: string | null
}

export interface MaintenanceTask {
  id: string
  task_code?: string
  title: string
  device_id?: string | null
  device_name?: string | null
  device_code?: string | null
  manufacturer?: string | null
  product_series?: string | null
  model?: string | null
  device_type: string
  fault_type?: string | null
  alarm_code?: string | null
  fault_description?: string | null
  priority: string
  status: string
  task_status: string
  assignee?: string | null
  assignee_id?: string | null
  assignee_name?: string | null
  created_by?: string | null
  created_by_name?: string | null
  created_at: string
  updated_at: string
  started_at?: string | null
  completed_at?: string | null
  planned_start_at?: string | null
  planned_end_at?: string | null
  due_date?: string | null
  diagnosis_trace_id?: string | null
  qa_trace_id?: string | null
  source_type?: string | null
  source_trace_id?: string | null
  sop_template_id?: string | null
  suggested_steps?: string[]
  root_cause?: string | null
  repair_action?: string | null
  result_summary?: string | null
  completion_notes?: string | null
  verification_result?: string | null
  replaced_parts?: string[]
  is_recurrent?: boolean
}

export interface UploadedMediaItem {
  id: string
  file_name: string
  original_file_name?: string | null
  file_ext?: string | null
  mime_type?: string | null
  file_size?: number | null
  media_type: string
  description?: string | null
  ocr_text?: string | null
  manufacturer?: string | null
  product_series?: string | null
  device_type: string
  device_id?: string | null
  device_name?: string | null
  task_id?: string | null
  diagnosis_record_id?: string | null
  qa_trace_id?: string | null
  uploaded_by?: string | null
  uploaded_by_name?: string | null
  status: string
  fault_type?: string | null
  alarm_code?: string | null
  ocr_status?: string | null
  ocr_message?: string | null
  ocr_error_summary?: string | null
  ocr_provider?: string | null
  ocr_lang?: string | null
  ocr_processed_at?: string | null
  preview_url: string
  metadata_json?: Record<string, unknown>
  created_at?: string | null
  updated_at?: string | null
}

export interface MediaContextItem {
  id: string
  file_name: string
  original_file_name?: string | null
  media_type: string
  description?: string | null
  manufacturer?: string | null
  product_series?: string | null
  device_type: string
  device_id?: string | null
  device_name?: string | null
  task_id?: string | null
  fault_type?: string | null
  alarm_code?: string | null
  ocr_status: string
  ocr_message: string
  ocr_error_summary?: string | null
  ocr_provider?: string | null
  ocr_lang?: string | null
  ocr_processed_at?: string | null
  ocr_text?: string | null
  preview_url: string
  created_at?: string | null
}

export interface OCRContextItem {
  media_id: string
  file_name?: string | null
  ocr_status: string
  provider?: string | null
  lang?: string | null
  text: string
  notice?: string | null
  processed_at?: string | null
}

export interface OCRStatusResult {
  enabled: boolean
  provider: string
  status: string
  message: string
  lang: string
  command: string
  timeout_seconds: number
  max_image_mb: number
  available: boolean
  error_summary?: string | null
  metadata?: Record<string, unknown>
}

export interface MediaOCRResult {
  media_id: string
  status: string
  provider: string
  lang: string
  text: string
  message: string
  error_summary?: string | null
  processed_at?: string | null
  metadata?: Record<string, unknown>
}

export interface MediaUploadResult {
  media_id: string
  media_type: string
  description?: string | null
  status: string
  file_name: string
  original_file_name?: string | null
  ocr_text?: string | null
  ocr_status: string
  message: string
  preview_url: string
  manufacturer?: string | null
  product_series?: string | null
  device_type: string
  device_id?: string | null
  task_id?: string | null
  fault_type?: string | null
  alarm_code?: string | null
}

export interface AssignableUser {
  id: string
  username: string
  display_name?: string | null
  role: 'admin' | 'expert' | 'engineer' | string
}

export interface SOPTemplate {
  id: string
  title: string
  manufacturer?: string | null
  product_series?: string | null
  device_type: string
  fault_type?: string | null
  maintenance_level: string
  steps: Record<string, unknown>[]
  safety_requirements: Record<string, unknown>[]
  tools_required: Record<string, unknown>[]
  materials_required: Record<string, unknown>[]
  compliance_notes?: string | null
  status: string
  version: number
  created_at: string
  updated_at: string
}

export interface SOPGenerateResult {
  source: string
  template_id?: string | null
  title: string
  manufacturer?: string | null
  product_series?: string | null
  model?: string | null
  device_type: string
  fault_type: string
  alarm_code?: string | null
  maintenance_level: string
  steps: Record<string, unknown>[]
  safety_requirements: Record<string, unknown>[]
  tools_required: Record<string, unknown>[]
  materials_required: Record<string, unknown>[]
  compliance_notes?: string | null
  references: RetrievalReference[]
  media_items: MediaContextItem[]
  media_notice?: string | null
  kg_context?: KGBusinessContext
  kg_tools?: KGBusinessNode[]
  kg_parts?: KGBusinessNode[]
  kg_safety_risks?: KGBusinessNode[]
  kg_steps?: KGBusinessNode[]
  kg_evidence?: KGEvidence[]
  confidence: number
  model_provider: string
  model_name: string
  model_enhanced: boolean
  model_call_trace_id?: string | null
}

export interface RecordCenterOverview {
  qa_records?: number
  diagnosis_records?: number
  maintenance_tasks?: number
  maintenance_records?: number
  sop_executions?: number
  knowledge_documents?: number
  knowledge_contributions?: number
  uploaded_media?: number
  devices?: number
  totals?: Record<string, number>
  recent_records?: RecordCenterItem[]
  [key: string]: unknown
}

export interface RecordCenterItem {
  record_type: string
  record_id: string
  trace_id?: string | null
  title: string
  summary?: string | null
  device_id?: string | null
  device_name?: string | null
  status?: string | null
  fault_type?: string | null
  alarm_code?: string | null
  manufacturer?: string | null
  product_series?: string | null
  created_by_name?: string | null
  created_at?: string | null
}

export interface RecordCenterDetail {
  record_type: string
  record_id: string
  record: Record<string, unknown>
  related_records: RecordCenterItem[]
  summary_item?: RecordCenterItem
}

export interface DeviceTimelineItem {
  time?: string | null
  record_type: string
  record_id: string
  title: string
  summary?: string | null
  trace_id?: string | null
  status?: string | null
  operator_name?: string | null
}

export interface DeviceTimelineResponse {
  device: Record<string, unknown>
  timeline: DeviceTimelineItem[]
}

export interface ModelProviderStatus {
  provider: string
  enabled: boolean
  configured: boolean
  available: boolean
  availability_status?: string
  model_name?: string | null
  base_url?: string | null
  base_url_configured?: boolean
  model_configured?: boolean
  api_type?: string | null
  api_key_configured?: boolean
  health_path?: string | null
  latency_ms?: number | null
  error_summary?: string | null
  message: string
}

export interface ModelGatewayStatus {
  default_provider: string
  fallback_enabled?: boolean
  allow_fallback?: boolean
  logging_enabled: boolean
  timeout_seconds: number
  providers: ModelProviderStatus[]
}

export interface ModelGatewayResponse {
  trace_id: string
  provider: string
  requested_provider: string
  model_name: string
  task_type: string
  content: string
  success: boolean
  fallback_used?: boolean
  latency_ms?: number | null
  error_message?: string | null
  usage?: Record<string, unknown> | null
}

export interface SystemStatus {
  service_status?: string
  database_status?: string
  database_checked_at?: string
  database_latency_ms?: number | null
  database_error?: string | null
  document_count?: number
  chunk_count?: number
  qa_record_count?: number
  diagnosis_record_count?: number
  maintenance_task_count?: number
  media_count?: number
  sop_template_count?: number
  name?: string
  status?: string
  version?: string
  environment?: string
  security?: Record<string, unknown>
}

export interface SystemStatistics {
  devices?: Record<string, number>
  knowledge?: Record<string, number>
  qa?: Record<string, number>
  diagnosis?: Record<string, number>
  tasks?: Record<string, number>
  maintenance?: Record<string, number>
  media?: Record<string, number>
  sop?: Record<string, number>
  corrections?: Record<string, number>
  [key: string]: unknown
}

export interface KGNode {
  id: string
  node_type: string
  canonical_name: string
  display_name?: string | null
  manufacturer?: string | null
  product_series?: string | null
  device_type: string
  properties_json?: Record<string, unknown>
  confidence: number
  status: string
  source_type?: string | null
  source_id?: string | null
  aliases?: string[]
  evidence_count?: number
  created_at: string
  updated_at: string
}

export interface KGEdge {
  id: string
  source_node_id: string
  target_node_id: string
  source_node_name?: string | null
  target_node_name?: string | null
  relation_type: string
  display_relation?: string | null
  properties_json?: Record<string, unknown>
  confidence: number
  evidence_count: number
  status: string
  source_type?: string | null
  source_id?: string | null
  created_at: string
  updated_at: string
}

export interface KGGraphEdge {
  id: string
  source_node_id: string
  target_node_id: string
  source_node_name?: string | null
  target_node_name?: string | null
  relation_type: string
  display_relation?: string | null
  confidence: number
  evidence_count: number
  status?: string
}

export interface KGEvidence {
  id: string
  node_id?: string | null
  edge_id?: string | null
  source_type: string
  source_id?: string | null
  document_id?: string | null
  chunk_id?: string | null
  contribution_id?: string | null
  diagnosis_trace_id?: string | null
  task_id?: string | null
  maintenance_record_id?: string | null
  media_id?: string | null
  evidence_text?: string | null
  confidence: number
  created_at: string
}

export interface KGExtractionRun {
  id: string
  source_type: string
  source_id?: string | null
  extractor: string
  status: string
  candidate_count: number
  approved_count: number
  rejected_count: number
  error_summary?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_by?: string | null
  metadata_json?: Record<string, unknown> | null
  created_at: string
}

export interface KGCandidate {
  id: string
  run_id: string
  candidate_type: 'node' | 'edge' | 'alias'
  payload_json: Record<string, unknown>
  status: string
  confidence: number
  evidence_text?: string | null
  approved_node_id?: string | null
  approved_edge_id?: string | null
  reviewed_by?: string | null
  reviewed_at?: string | null
  review_comment?: string | null
  created_at: string
}

export interface KGOverview {
  node_count: number
  edge_count: number
  evidence_count: number
  pending_candidate_count: number
  completed_run_count: number
  node_type_counts: Record<string, number>
  relation_type_counts: Record<string, number>
  recent_runs: KGExtractionRun[]
}

export interface KGNeighborhood {
  center: KGNode
  nodes: KGNode[]
  edges: KGEdge[]
}

export interface KGPathItem {
  nodes: KGNode[]
  edges: KGEdge[]
  summary?: string
}

export interface KGPathResponse {
  found: boolean
  nodes: KGNode[]
  edges: KGEdge[]
}

export interface KGGraphResponse {
  nodes: KGNode[]
  edges: KGGraphEdge[]
  statistics: Record<string, unknown>
  legend: Record<string, unknown>
}

export interface KGSearchResponse {
  keyword?: string | null
  nodes: KGNode[]
  edges: KGEdge[]
  evidence: KGEvidence[]
}

export interface KGBusinessNode {
  id: string
  node_type: string
  display_name: string
  canonical_name?: string
  manufacturer?: string | null
  product_series?: string | null
  device_type?: string | null
  confidence?: number
  evidence_count?: number
  via_relation?: string | null
  via_relation_label?: string | null
}

export interface KGBusinessContext {
  matched_nodes: KGBusinessNode[]
  related_faults: KGBusinessNode[]
  related_alarms: KGBusinessNode[]
  related_causes: KGBusinessNode[]
  inspection_items: KGBusinessNode[]
  recommended_actions: KGBusinessNode[]
  safety_risks: KGBusinessNode[]
  related_sop: KGBusinessNode[]
  tools: KGBusinessNode[]
  parts: KGBusinessNode[]
  evidence: KGEvidence[]
  graph_paths: KGPathItem[]
  kg_nodes: KGNode[]
  kg_edges: KGEdge[]
  summary: Record<string, unknown>
}

export interface KGExtractionResult {
  run: KGExtractionRun
  candidates: KGCandidate[]
}

export const manufacturerOptions = [
  { label: '华为', value: 'huawei' },
  { label: '阳光电源', value: 'sungrow' }
]

export const productSeriesOptions = [
  { label: 'SUN2000', value: 'SUN2000', manufacturer: 'huawei' },
  { label: 'FusionSolar', value: 'FusionSolar', manufacturer: 'huawei' },
  { label: 'SG', value: 'SG', manufacturer: 'sungrow' }
]

export const deviceTypeOptions = [{ label: '光伏逆变器', value: 'pv_inverter' }]

export const documentTypeOptions = [
  { label: '设备手册', value: 'manual' },
  { label: '告警代码', value: 'alarm_code' },
  { label: '检修规程', value: 'sop' },
  { label: '故障案例', value: 'fault_case' },
  { label: '巡检规范', value: 'inspection_standard' },
  { label: '检修记录', value: 'maintenance_record' }
]

export const contributionTypeOptions = [
  { label: '一线检修经验', value: 'maintenance_experience' },
  { label: '故障案例补充', value: 'fault_case' },
  { label: '告警处理经验', value: 'alarm_experience' },
  { label: '规程优化建议', value: 'sop_suggestion' }
]

export const faultTypeOptions = [
  { label: '低绝缘阻抗', value: 'low_insulation_resistance' },
  { label: '直流侧异常', value: 'dc_abnormal' },
  { label: '交流过压', value: 'ac_overvoltage' },
  { label: '交流欠压', value: 'ac_undervoltage' },
  { label: '并网故障', value: 'grid_connection_fault' },
  { label: '过温', value: 'over_temperature' },
  { label: '风扇故障', value: 'fan_fault' },
  { label: '通信中断', value: 'communication_interruption' },
  { label: '设备离线', value: 'device_offline' },
  { label: 'MPPT 异常', value: 'mppt_abnormal' },
  { label: '发电量低', value: 'low_power_generation' },
  { label: '告警代码查询', value: 'alarm_code_query' },
  { label: '未知', value: 'unknown' }
]

export const priorityOptions = [
  { label: '低', value: 'low' },
  { label: '中', value: 'medium' },
  { label: '高', value: 'high' },
  { label: '紧急', value: 'urgent' }
]
