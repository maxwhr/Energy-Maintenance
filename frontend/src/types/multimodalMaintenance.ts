export type MultimodalCaseStatus =
  | 'DRAFT'
  | 'MEDIA_UPLOADED'
  | 'ANALYZING'
  | 'NEEDS_CLARIFICATION'
  | 'EVIDENCE_READY'
  | 'DIAGNOSIS_READY'
  | 'MULTIPLE_POSSIBILITIES'
  | 'INSUFFICIENT_EVIDENCE'
  | 'SOP_DRAFT_READY'
  | 'TASK_DRAFT_READY'
  | 'ARCHIVED'
  | 'FAILED'

export interface MultimodalMaintenanceCase {
  id: string
  case_id: string
  title: string
  status: MultimodalCaseStatus
  user_query?: string | null
  normalized_query?: string | null
  conversation_id?: string | null
  device_id?: string | null
  device_model?: string | null
  product_family?: string | null
  equipment_category?: string | null
  alarm_codes: string[]
  components: string[]
  reported_symptoms: string[]
  occurrence_conditions: string[]
  user_confirmed_facts: Record<string, unknown>
  missing_information: string[]
  clarifying_questions: MultimodalClarifyingQuestion[]
  media_ids: string[]
  knowledge_citations: MultimodalCitation[]
  safety_level: string
  confidence_status: string
  diagnosis_status: string
  sop_draft_id?: string | null
  task_draft_id?: string | null
  analysis_job_ids: string[]
  metadata_json: Record<string, any>
  last_error_code?: string | null
  last_error_message?: string | null
  created_by: string
  created_at: string
  updated_at: string
  evidence_count: number
  region_count: number
  conflict_count: number
  hypothesis_count: number
}

export interface MultimodalClarifyingQuestion {
  question_id: string
  question_type: string
  question: string
  required: boolean
  safe_template: boolean
}

export interface MultimodalCaseMedia {
  media_id: string
  media_type: string
  original_file_name?: string | null
  mime_type?: string | null
  file_size?: number | null
  status: string
  preview_url: string
  ocr_status?: string | null
  quality_flags: string[]
  ocr_ready?: boolean | null
  vision_ready?: boolean | null
  created_at?: string | null
}

export interface MultimodalEvidenceItem {
  id: string
  evidence_id: string
  case_id: string
  media_id?: string | null
  region_id?: string | null
  modality: string
  evidence_type: string
  source_type: string
  source_hash: string
  observed_text?: string | null
  normalized_text?: string | null
  visual_attributes: Record<string, unknown>
  bounding_box?: number[] | Record<string, number> | null
  page_or_frame_locator: Record<string, unknown>
  device_model_candidates: string[]
  alarm_code_candidates: string[]
  component_candidates: string[]
  indicator_state_candidates: string[]
  symptom_candidates: string[]
  confidence: number
  observation_status: string
  provider?: string | null
  provider_model?: string | null
  user_confirmed: boolean
  contradicted: boolean
  contradiction_reason?: string | null
  metadata_json: Record<string, any>
  created_at: string
}

export interface MultimodalConflict {
  conflict_id: string
  conflict_type: string
  evidence_ids: string[]
  severity: string
  resolution_required: boolean
  recommended_question?: string | null
  resolution_status: string
}

export interface MultimodalCitation {
  citation_id?: string
  chunk_id: string
  document_id: string
  document_title?: string | null
  section_title?: string | null
  page_number?: number | null
  source_locator: Record<string, unknown>
  quote?: string | null
  source_type?: string
}

export interface MultimodalRetrievalResult {
  generated_queries: Array<{ query_type: string; query: string; evidence_ids: string[]; hypothesis_signals: string[] }>
  requested_channels: string[]
  actual_channels: string[]
  raw_candidates: Record<string, any>[]
  surfaced_results: Record<string, any>[]
  citations: MultimodalCitation[]
  citation_validity_ratio: number
  citation_coverage_ratio: number
  confidence_status: string
  stage_latency: Record<string, number>
  dedicated_rerank: Record<string, any>
  external_call_counts: Record<string, number>
  answer?: string
  references?: MultimodalCitation[]
  suggested_steps?: string[]
  safety_notes?: string[]
  trace_id?: string | null
  qa_record_id?: string | null
  persistence_status?: string
}

export interface MultimodalHypothesis {
  hypothesis_id: string
  fault_category: string
  fault_name: string
  applicable_device?: string | null
  supporting_evidence_ids: string[]
  contradicting_evidence_ids: string[]
  knowledge_citation_ids: string[]
  confidence: number
  confidence_level: string
  status: string
  recommended_checks: string[]
  safety_warnings: string[]
  missing_information: string[]
}

export interface MultimodalDiagnosisResult {
  observed_facts: Record<string, any>[]
  possible_faults: MultimodalHypothesis[]
  recommended_checks: string[]
  recommended_actions: string[]
  safety_warnings: string[]
  missing_information: string[]
  citations: MultimodalCitation[]
  confidence_status: string
  unsupported_diagnosis_count: number
  safety: Record<string, any>
  confidence: Record<string, any>
  case_status: string
}

export interface MultimodalDraftResult {
  case_id: string
  boundary: {
    allowed: boolean
    artifact_type: string
    blocked_reasons: string[]
    requires_human_approval: boolean
    formal_record_created: boolean
  }
  artifact?: {
    artifact_id: string
    artifact_type: string
    title?: string | null
    content_text?: string | null
    content: Record<string, any>
    created_at?: string | null
  } | null
  cached?: boolean
}

export interface MultimodalAuditItem {
  id: string
  action: string
  operator?: string | null
  trace_id?: string | null
  detail: Record<string, any>
  created_at?: string | null
}
