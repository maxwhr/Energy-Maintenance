import request from '@/utils/request'
import type {
  KGEdge,
  KGEvidence,
  KGExtractionResult,
  KGExtractionRun,
  KGBusinessContext,
  KGGraphResponse,
  KGPathResponse,
  KGSearchResponse,
  KGNeighborhood,
  KGNode,
  KGOverview,
  KGCandidate,
  PageResponse
} from '@/types'

export const getKnowledgeGraphOverviewApi = () => request.get<KGOverview>('/kg/overview')

export const getKnowledgeGraphGraphApi = (params?: Record<string, unknown>) =>
  request.get<KGGraphResponse>('/kg/graph', { params })

export const bootstrapKnowledgeGraphApi = (params?: Record<string, unknown>) =>
  request.post<Record<string, unknown>>('/kg/bootstrap', undefined, { params })

export const searchKnowledgeGraphApi = (params?: Record<string, unknown>) =>
  request.get<KGSearchResponse>('/kg/search', { params })

export const getKnowledgeGraphBusinessContextApi = (params?: Record<string, unknown>) =>
  request.get<KGBusinessContext>('/kg/business-context', { params })

export const getKnowledgeGraphNodesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KGNode>>('/kg/nodes', { params })

export const createKnowledgeGraphNodeApi = (payload: Record<string, unknown>) =>
  request.post<KGNode>('/kg/nodes', payload)

export const updateKnowledgeGraphNodeApi = (nodeId: string, payload: Record<string, unknown>) =>
  request.put<KGNode>(`/kg/nodes/${nodeId}`, payload)

export const archiveKnowledgeGraphNodeApi = (nodeId: string) =>
  request.post<KGNode>(`/kg/nodes/${nodeId}/archive`)

export const getKnowledgeGraphEdgesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KGEdge>>('/kg/edges', { params })

export const createKnowledgeGraphEdgeApi = (payload: Record<string, unknown>) =>
  request.post<KGEdge>('/kg/edges', payload)

export const updateKnowledgeGraphEdgeApi = (edgeId: string, payload: Record<string, unknown>) =>
  request.put<KGEdge>(`/kg/edges/${edgeId}`, payload)

export const archiveKnowledgeGraphEdgeApi = (edgeId: string) =>
  request.post<KGEdge>(`/kg/edges/${edgeId}/archive`)

export const getKnowledgeGraphEvidenceApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KGEvidence>>('/kg/evidence', { params })

export const getKnowledgeGraphNeighborhoodApi = (nodeId: string, params?: Record<string, unknown>) =>
  request.get<KGNeighborhood>(`/kg/neighborhood/${nodeId}`, { params })

export const getKnowledgeGraphPathApi = (params: Record<string, unknown>) =>
  request.get<KGPathResponse>('/kg/path', { params })

export const getKnowledgeGraphExtractionRunsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KGExtractionRun>>('/kg/extraction-runs', { params })

export const getKnowledgeGraphCandidatesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<KGCandidate>>('/kg/candidates', { params })

export const extractKnowledgeGraphFromDocumentApi = (documentId: string, payload?: Record<string, unknown>) =>
  request.post<KGExtractionResult>(`/kg/extract/from-document/${documentId}`, payload ?? {})

export const extractKnowledgeGraphFromContributionApi = (contributionId: string, payload?: Record<string, unknown>) =>
  request.post<KGExtractionResult>(`/kg/extract/from-contribution/${contributionId}`, payload ?? {})

export const approveKnowledgeGraphCandidateApi = (candidateId: string, comment?: string) =>
  request.post<KGCandidate>(`/kg/candidates/${candidateId}/approve`, undefined, {
    params: comment ? { comment } : undefined
  })

export const rejectKnowledgeGraphCandidateApi = (candidateId: string, comment?: string) =>
  request.post<KGCandidate>(`/kg/candidates/${candidateId}/reject`, undefined, {
    params: comment ? { comment } : undefined
  })
