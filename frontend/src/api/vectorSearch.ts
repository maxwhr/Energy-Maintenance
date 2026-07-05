import request from '@/utils/request'
import type {
  DocumentVectorIndexStatus,
  PageResponse,
  VectorIndexJobResult,
  VectorIndexRun,
  VectorSearchStatus,
  VectorTestQueryResult,
} from '@/types'

export const getVectorSearchStatusApi = () =>
  request.get<VectorSearchStatus>('/vector-search/status')

export const getVectorIndexRunsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<VectorIndexRun>>('/vector-search/runs', { params })

export const getVectorIndexRunApi = (runId: string) =>
  request.get<VectorIndexRun>(`/vector-search/runs/${runId}`)

export const getDocumentVectorStatusApi = (documentId: string) =>
  request.get<DocumentVectorIndexStatus>(`/vector-search/documents/${documentId}/status`)

export const getChunkVectorStatusApi = (chunkId: string) =>
  request.get<Record<string, unknown>[]>(`/vector-search/chunks/${chunkId}/status`)

export const indexDocumentVectorApi = (documentId: string, data?: Record<string, unknown>) =>
  request.post<VectorIndexJobResult>(`/vector-search/documents/${documentId}/index`, data ?? {})

export const indexChunkVectorApi = (chunkId: string, data?: Record<string, unknown>) =>
  request.post<VectorIndexJobResult>(`/vector-search/chunks/${chunkId}/index`, data ?? {})

export const reindexStaleVectorApi = (data?: Record<string, unknown>) =>
  request.post<VectorIndexJobResult>('/vector-search/reindex-stale', data ?? {})

export const testVectorQueryApi = (data: Record<string, unknown>) =>
  request.post<VectorTestQueryResult>('/vector-search/test-query', data)
