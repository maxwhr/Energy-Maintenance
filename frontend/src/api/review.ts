import request from '@/utils/request'
import type { PageResponse } from '@/types'

export const getReviewKnowledgeApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/review/knowledge', { params })

export const getReviewKnowledgeDetailApi = (documentId: string) =>
  request.get<Record<string, unknown>>(`/review/knowledge/${documentId}`)

export const approveKnowledgeApi = (documentId: string, review_comment?: string) =>
  request.post<Record<string, unknown>>(`/review/knowledge/${documentId}/approve`, { comment: review_comment })

export const rejectKnowledgeApi = (documentId: string, review_comment?: string) =>
  request.post<Record<string, unknown>>(`/review/knowledge/${documentId}/reject`, { comment: review_comment })

export const archiveKnowledgeApi = (documentId: string, review_comment?: string) =>
  request.post<Record<string, unknown>>(`/review/knowledge/${documentId}/archive`, { comment: review_comment })
