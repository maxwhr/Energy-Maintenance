import request from '@/utils/request'
import type { DiagnosisResponse, PageResponse } from '@/types'

export const analyzeDiagnosisApi = (data: Record<string, unknown>) =>
  request.post<DiagnosisResponse>('/diagnosis/analyze', data)

export const getDiagnosisRecordsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/diagnosis/records', { params })

export const getDiagnosisRecordApi = (traceId: string) =>
  request.get<Record<string, unknown>>(`/diagnosis/records/${traceId}`)
