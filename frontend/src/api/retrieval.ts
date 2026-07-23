import request from '@/utils/request'
import type {
  PageResponse,
  QueryAwareRetrievalRequest,
  QueryAwareRetrievalResponse,
  RetrievalQueryRequest,
  RetrievalResponse
} from '@/types'

export const queryRetrievalApi = (data: RetrievalQueryRequest) =>
  request.post<RetrievalResponse>('/retrieval/query', data)

export const getRetrievalRecordsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/retrieval/records', { params })

export const getRetrievalRecordApi = (traceId: string) =>
  request.get<Record<string, unknown>>(`/retrieval/records/${traceId}`)

export const getRetrievalEvaluationRunsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/retrieval/evaluation-runs', { params })

export const getRetrievalEvaluationRunApi = (runId: string) =>
  request.get<Record<string, unknown>>(`/retrieval/evaluation-runs/${runId}`)

export const getRetrievalEvaluationCasesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/retrieval/evaluation-cases', { params })

export const runRetrievalEvaluationApi = (data: Record<string, unknown>) =>
  request.post<Record<string, unknown>>('/retrieval/evaluate', data)

export const getRetrievalStrategyStatusApi = () =>
  request.get<Record<string, any>>('/retrieval/strategy-status')

export const getRetrievalR1ScopeStatusApi = () =>
  request.get<Record<string, any>>('/retrieval/scope/r1-status')

export const getRetrievalR2ScopeStatusApi = () =>
  request.get<Record<string, any>>('/retrieval/scope/r2-status')

export const getRetrievalR3ScopeStatusApi = () =>
  request.get<Record<string, any>>('/retrieval/scope/r3-status')

export const getRetrievalR4ScopeStatusApi = () =>
  request.get<Record<string, any>>('/retrieval/scope/r4-status')

export const understandRetrievalQueryApi = (data: Record<string, unknown>) =>
  request.post<Record<string, any>>('/retrieval/understand', data, { timeout: 10000 })

export const planRetrievalQueryApi = (data: Record<string, unknown>) =>
  request.post<Record<string, any>>('/retrieval/plan', data, { timeout: 10000 })

export const queryAwareRetrievalApi = (data: QueryAwareRetrievalRequest, signal?: AbortSignal) =>
  request.post<QueryAwareRetrievalResponse>('/retrieval/query-aware-search', data, { timeout: 30000, signal })

export const clarifyRetrievalQueryApi = (data: Record<string, unknown>, signal?: AbortSignal) =>
  request.post<QueryAwareRetrievalResponse>('/retrieval/clarify', data, { timeout: 30000, signal })

export const rerankRetrievalCandidatesApi = (data: Record<string, unknown>) =>
  request.post<Record<string, any>>('/retrieval/rerank', data, { timeout: 15000 })

export const getR5RetrievalQualitySummaryApi = () =>
  request.get<Record<string, any>>('/system/retrieval-quality/r5/summary')

export const getRagPerformanceSummaryApi = () =>
  request.get<Record<string, any>>('/system/retrieval-performance/summary')

export const getRetrievalPilotStatusApi = () =>
  request.get<Record<string, any>>('/retrieval/pilot/status')

export const getRetrievalPilotU3StatusApi = () =>
  request.get<Record<string, any>>('/retrieval/pilot/u3/status')

export const getRetrievalBenchmarkCasesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, any>>>('/retrieval/benchmark/cases', { params })

export const getRetrievalBenchmarkProgressApi = () =>
  request.get<Record<string, any>>('/retrieval/benchmark/review-progress')

export const reviewRetrievalBenchmarkCaseApi = (
  caseId: string,
  kind: 'engineering' | 'expert',
  data: Record<string, unknown>
) => request.post<Record<string, any>>(`/retrieval/benchmark/cases/${caseId}/${kind}-review`, data)

export const freezeRetrievalBenchmarkApi = (datasetVersion = 'official_pilot_test_v1') =>
  request.post<Record<string, any>>('/retrieval/benchmark/freeze', { dataset_version: datasetVersion })

export const createRetrievalPilotSessionApi = (data: Record<string, unknown>) =>
  request.post<Record<string, any>>('/retrieval/pilot-sessions', data)

export const activateRetrievalPilotSessionApi = (sessionId: string) =>
  request.post<Record<string, any>>(`/retrieval/pilot-sessions/${sessionId}/activate`, {})

export const rollbackRetrievalPilotSessionApi = (sessionId: string, reason: string) =>
  request.post<Record<string, any>>(`/retrieval/pilot-sessions/${sessionId}/rollback`, { reason })
