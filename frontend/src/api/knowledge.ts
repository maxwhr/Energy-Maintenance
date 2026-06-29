import request from '@/utils/request'
import type { KnowledgeChunk, KnowledgeDocument, KnowledgeUploadResult, PageResponse } from '@/types'

export const getDocumentsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KnowledgeDocument>>('/knowledge/documents', { params })

export const getDocumentApi = (documentId: string) =>
  request.get<KnowledgeDocument>(`/knowledge/documents/${documentId}`)

export const uploadDocumentApi = (formData: FormData) =>
  request.post<KnowledgeUploadResult>('/knowledge/documents/upload', formData)

export const getDocumentChunksApi = (documentId: string, params?: Record<string, unknown>) =>
  request.get<PageResponse<KnowledgeChunk>>(`/knowledge/documents/${documentId}/chunks`, { params })

export const reparseDocumentApi = (documentId: string) =>
  request.post<Record<string, unknown>>(`/knowledge/documents/${documentId}/reparse`)

export const deleteDocumentApi = (documentId: string) =>
  request.delete<Record<string, unknown>>(`/knowledge/documents/${documentId}`)
