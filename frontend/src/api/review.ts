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

export const batchApproveVendorOfficialApi = (documentIds: string[], comment?: string) =>
  request.post<Record<string, unknown>>('/review/knowledge/vendor-official/batch-approve-for-pilot', {
    document_ids: documentIds,
    comment
  })

export const flagVendorOfficialApi = (documentId: string, action: 'needs_metadata' | 'marketing_only' | 'needs_ocr', comment?: string) =>
  request.post<Record<string, unknown>>(`/review/knowledge/${documentId}/vendor-official-flag`, { action, comment })

export const withdrawVendorOfficialApprovalApi = (documentId: string, reason: string, targetStatus: 'pending_review' | 'needs_revision' = 'pending_review') =>
  request.post<Record<string, unknown>>(`/review/knowledge/${documentId}/withdraw-approval`, {
    target_status: targetStatus,
    reason
  })
