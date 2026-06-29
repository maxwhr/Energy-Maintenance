import request from '@/utils/request'
import type { PageResponse, RetrievalResponse } from '@/types'

export const queryRetrievalApi = (data: Record<string, unknown>) =>
  request.post<RetrievalResponse>('/retrieval/query', data)

export const getRetrievalRecordsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/retrieval/records', { params })

export const getRetrievalRecordApi = (traceId: string) =>
  request.get<Record<string, unknown>>(`/retrieval/records/${traceId}`)
