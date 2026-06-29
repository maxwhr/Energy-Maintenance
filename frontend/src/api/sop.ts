import request from '@/utils/request'
import type { PageResponse, SOPGenerateResult, SOPTemplate } from '@/types'

export const getSopTemplatesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<SOPTemplate>>('/sop/templates', { params })

export const getSopTemplateApi = (id: string) => request.get<SOPTemplate>(`/sop/templates/${id}`)

export const createSopTemplateApi = (data: Record<string, unknown>) =>
  request.post<SOPTemplate>('/sop/templates', data)

export const updateSopTemplateApi = (id: string, data: Record<string, unknown>) =>
  request.put<SOPTemplate>(`/sop/templates/${id}`, data)

export const archiveSopTemplateApi = (id: string) =>
  request.post<SOPTemplate>(`/sop/templates/${id}/archive`)

export const generateSopApi = (data: Record<string, unknown>) =>
  request.post<SOPGenerateResult>('/sop/generate', data)

export const getSopExecutionsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/sop/executions', { params })

export const createSopExecutionApi = (data: Record<string, unknown>) =>
  request.post<Record<string, unknown>>('/sop/executions', data)

export const updateSopExecutionApi = (id: string, data: Record<string, unknown>) =>
  request.put<Record<string, unknown>>(`/sop/executions/${id}`, data)
