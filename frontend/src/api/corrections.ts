import request from '@/utils/request'
import type { PageResponse } from '@/types'

export const createCorrectionApi = (data: Record<string, unknown>) =>
  request.post<Record<string, unknown>>('/corrections', data)

export const getCorrectionsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/corrections', { params })

export const getCorrectionApi = (id: string) =>
  request.get<Record<string, unknown>>(`/corrections/${id}`)

export const resolveCorrectionApi = (id: string, data: Record<string, unknown>) =>
  request.post<Record<string, unknown>>(`/corrections/${id}/resolve`, data)
