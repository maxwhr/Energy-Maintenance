import request from '@/utils/request'
import type {
  ExternalApiCallLog,
  ExternalApiCheckResult,
  ExternalApiDryRunPayload,
  ExternalApiGatewayResult,
  ExternalApiHealthCheck,
  ExternalApiProvider,
  ExternalApiRealCheckPayload,
  ExternalApiRealRunPayload,
  ExternalApiRoute,
  ExternalApiStatus,
  PageResponse
} from '@/types'

export const getExternalApiProviders = (params?: Record<string, unknown>) =>
  request.get<ExternalApiProvider[]>('/external-apis/providers', { params })

export const getExternalApiProvider = (providerCode: string) =>
  request.get<ExternalApiProvider>(`/external-apis/providers/${providerCode}`)

export const getExternalApiRoutes = (params?: Record<string, unknown>) =>
  request.get<ExternalApiRoute[]>('/external-apis/routes', { params })

export const getExternalApiStatus = () =>
  request.get<ExternalApiStatus>('/external-apis/status')

export const checkExternalApiProvider = (providerCode: string) =>
  request.post<ExternalApiCheckResult>(`/external-apis/providers/${providerCode}/check`)

export const dryRunExternalApi = (data: ExternalApiDryRunPayload) =>
  request.post<ExternalApiGatewayResult>('/external-apis/dry-run', data)

export const mockRunExternalApi = (data: ExternalApiDryRunPayload) =>
  request.post<ExternalApiGatewayResult>('/external-apis/mock-run', { ...data, mock_run: true })

export const realRunExternalApi = (data: ExternalApiRealRunPayload) =>
  request.post<ExternalApiGatewayResult>('/external-apis/real-run', data)

export const checkRealExternalApi = (data: ExternalApiRealCheckPayload) =>
  request.post<ExternalApiGatewayResult>('/external-apis/check-real', data)

export const getExternalApiLogs = (params?: Record<string, unknown>) =>
  request.get<PageResponse<ExternalApiCallLog>>('/external-apis/logs', { params })

export const getExternalApiLogDetail = (traceId: string) =>
  request.get<ExternalApiCallLog>(`/external-apis/logs/${traceId}`)

export const getExternalApiHealthChecks = (params?: Record<string, unknown>) =>
  request.get<PageResponse<ExternalApiHealthCheck>>('/external-apis/health-checks', { params })
