import request from '@/utils/request'
import type {
  MultimodalAuditItem,
  MultimodalCaseMedia,
  MultimodalDiagnosisResult,
  MultimodalDraftResult,
  MultimodalEvidenceItem,
  MultimodalMaintenanceCase,
  MultimodalRetrievalResult
} from '@/types/multimodalMaintenance'

export const getMultimodalCases = (params?: Record<string, unknown>) =>
  request.get<{ items: MultimodalMaintenanceCase[]; total: number; page: number; page_size: number }>('/multimodal/cases', { params })

export const createMultimodalCase = (data: Record<string, unknown>) =>
  request.post<MultimodalMaintenanceCase>('/multimodal/cases', data)

export const getMultimodalCase = (caseId: string) =>
  request.get<MultimodalMaintenanceCase>(`/multimodal/cases/${caseId}`)

export const uploadMultimodalCaseMedia = (caseId: string, data: FormData) =>
  request.post<Record<string, any>>(`/multimodal/cases/${caseId}/media`, data)

export const getMultimodalCaseMedia = (caseId: string) =>
  request.get<{ items: MultimodalCaseMedia[]; total: number }>(`/multimodal/cases/${caseId}/media`)

export const analyzeMultimodalCase = (caseId: string) =>
  request.post<Record<string, any>>(`/multimodal/cases/${caseId}/analyze`, {
    dry_run: true,
    mock_run: false,
    allow_real_api: false,
    force: false
  })

export const getMultimodalCaseEvidence = (caseId: string) =>
  request.get<{ items: MultimodalEvidenceItem[]; total: number; conflicts: any[] }>(`/multimodal/cases/${caseId}/evidence`)

export const confirmMultimodalEvidence = (caseId: string, evidenceId: string, confirmedValue?: string) =>
  request.post<MultimodalEvidenceItem>(`/multimodal/cases/${caseId}/evidence/${evidenceId}/confirm`, {
    confirmed_value: confirmedValue || null,
    reason: '用户在多模态检修工作台确认'
  })

export const rejectMultimodalEvidence = (caseId: string, evidenceId: string) =>
  request.post<MultimodalEvidenceItem>(`/multimodal/cases/${caseId}/evidence/${evidenceId}/reject`, {
    reason: '用户在多模态检修工作台标记识别错误'
  })

export const clarifyMultimodalCase = (caseId: string, answers: Record<string, string>) =>
  request.post<MultimodalMaintenanceCase>(`/multimodal/cases/${caseId}/clarify`, { answers, confirmed_facts: {} })

export const retrieveMultimodalCase = (caseId: string) =>
  request.post<MultimodalRetrievalResult>(`/multimodal/cases/${caseId}/retrieve`, {
    top_k: 5,
    requested_information: ['CAUSE', 'ACTION', 'SAFETY']
  })

export const diagnoseMultimodalCase = (caseId: string) =>
  request.post<MultimodalDiagnosisResult>(`/multimodal/cases/${caseId}/diagnose`, { proposed_actions: [] })

export const createMultimodalSopDraft = (caseId: string) =>
  request.post<MultimodalDraftResult>(`/multimodal/cases/${caseId}/sop-draft`, {})

export const createMultimodalTaskDraft = (caseId: string, sopUserConfirmed: boolean) =>
  request.post<MultimodalDraftResult>(`/multimodal/cases/${caseId}/task-draft`, {
    sop_user_confirmed: sopUserConfirmed,
    assigned_role: 'engineer'
  })

export const getMultimodalCaseAudit = (caseId: string) =>
  request.get<{ items: MultimodalAuditItem[]; total: number }>(`/multimodal/cases/${caseId}/audit`)

export const getMultimodalQualityStatus = () =>
  request.get<Record<string, any>>('/system/multimodal-quality/status')
