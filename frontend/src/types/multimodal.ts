export interface MediaProcessingJob {
  id: string
  media_id: string
  job_type: string
  provider_code: string
  provider_name?: string | null
  model_name?: string | null
  status: string
  input_hash?: string | null
  progress: number
  started_at?: string | null
  finished_at?: string | null
  error_code?: string | null
  error_message?: string | null
  request_summary_json?: Record<string, unknown> | null
  result_summary_json?: Record<string, unknown> | null
  external_trace_id?: string | null
  agent_run_id?: string | null
  agent_tool_call_id?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface MediaProcessingJobPayload {
  job_type: 'ocr' | 'multimodal_analysis' | 'combined' | 'manual_review'
  provider_code?: string | null
  capability?: string | null
  analysis_type?: string | null
  dry_run?: boolean
  mock_run?: boolean
  real_run?: boolean
  agent_run_id?: string | null
  input_summary?: Record<string, unknown>
}

export interface MediaOCRResult {
  id: string
  media_id: string
  job_id?: string | null
  provider_code: string
  provider_name?: string | null
  model_name?: string | null
  language?: string | null
  text?: string | null
  confidence?: number | string | null
  regions_json?: Record<string, unknown> | unknown[] | null
  raw_result_json?: Record<string, unknown> | null
  status?: string | null
  external_trace_id?: string | null
  created_by?: string | null
  created_at: string
}

export interface MediaAIAnalysis {
  id: string
  media_id: string
  job_id?: string | null
  provider_code: string
  provider_name?: string | null
  model_name?: string | null
  analysis_type?: string | null
  summary?: string | null
  detected_text?: string | null
  detected_alarm_codes_json?: unknown[] | null
  detected_device_info_json?: Record<string, unknown> | null
  visual_findings_json?: Record<string, unknown> | unknown[] | null
  possible_faults_json?: Record<string, unknown> | unknown[] | null
  safety_risks_json?: Record<string, unknown> | unknown[] | null
  recommended_actions_json?: Record<string, unknown> | unknown[] | null
  limitations_json?: Record<string, unknown> | unknown[] | null
  confidence?: number | string | null
  raw_response_json?: Record<string, unknown> | null
  external_trace_id?: string | null
  human_review_status: string
  reviewed_by?: string | null
  reviewed_at?: string | null
  review_comment?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface MediaEvidenceLink {
  id: string
  media_id: string
  ocr_result_id?: string | null
  analysis_id?: string | null
  source_type: string
  source_id: string
  relation_type: string
  created_at: string
  created_by?: string | null
}

export interface MediaEvidenceLinkPayload {
  media_id: string
  ocr_result_id?: string | null
  analysis_id?: string | null
  source_type: string
  source_id: string
  relation_type: string
}

export interface MediaMultimodalSummary {
  media_id: string
  jobs: MediaProcessingJob[]
  ocr_results: MediaOCRResult[]
  analyses: MediaAIAnalysis[]
  evidence_links: MediaEvidenceLink[]
  provider_status: Record<string, unknown>
  latest_ocr_status?: string | null
  latest_analysis_status?: string | null
  machine_result_boundary: string
}
