import request from '@/utils/request'
import type { ModelGatewayResponse, ModelGatewayStatus, PageResponse } from '@/types'

export const getModelGatewayStatusApi = () =>
  request.get<ModelGatewayStatus>('/model-gateway/status')

export const testModelGatewayApi = (data: Record<string, unknown>) =>
  request.post<ModelGatewayResponse>('/model-gateway/test', data)

export const chatModelGatewayApi = (data: Record<string, unknown>) =>
  request.post<ModelGatewayResponse>('/model-gateway/chat', data)

export const getModelCallLogsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/model-gateway/logs', { params })

export const getModelCallLogApi = (id: string) =>
  request.get<Record<string, unknown>>(`/model-gateway/logs/${id}`)
