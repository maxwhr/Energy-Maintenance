import request from '@/utils/request'
import type {
  KnowledgeContribution,
  KnowledgeContributionPayload,
  PageResponse
} from '@/types'

export const getKnowledgeContributionsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KnowledgeContribution>>('/knowledge/contributions', { params })

export const getKnowledgeContributionApi = (id: string) =>
  request.get<KnowledgeContribution>(`/knowledge/contributions/${id}`)

export const createKnowledgeContributionApi = (data: KnowledgeContributionPayload) =>
  request.post<KnowledgeContribution>('/knowledge/contributions', data)

export const updateKnowledgeContributionApi = (id: string, data: Partial<KnowledgeContributionPayload>) =>
  request.put<KnowledgeContribution>(`/knowledge/contributions/${id}`, data)

export const submitKnowledgeContributionApi = (id: string) =>
  request.post<KnowledgeContribution>(`/knowledge/contributions/${id}/submit`, {})

export const requestContributionChangesApi = (id: string, comment?: string) =>
  request.post<KnowledgeContribution>(`/knowledge/contributions/${id}/request-changes`, { comment })

export const approveKnowledgeContributionApi = (id: string, comment?: string) =>
  request.post<KnowledgeContribution>(`/knowledge/contributions/${id}/approve`, { comment })

export const rejectKnowledgeContributionApi = (id: string, comment?: string) =>
  request.post<KnowledgeContribution>(`/knowledge/contributions/${id}/reject`, { comment })

export const convertKnowledgeContributionApi = (id: string, comment?: string) =>
  request.post<Record<string, unknown>>(`/knowledge/contributions/${id}/convert-to-document`, { comment })

export const archiveKnowledgeContributionApi = (id: string, comment?: string) =>
  request.post<KnowledgeContribution>(`/knowledge/contributions/${id}/archive`, { comment })
