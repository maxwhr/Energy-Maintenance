import request from '@/utils/request'
import type { BackendUser, PageResponse, SystemStatistics, SystemStatus } from '@/types'

export const getUsersApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<BackendUser>>('/users', { params })

export const createUserApi = (data: Record<string, unknown>) =>
  request.post<BackendUser>('/users', data)

export const updateUserApi = (id: string, data: Record<string, unknown>) =>
  request.put<BackendUser>(`/users/${id}`, data)

export const disableUserApi = (id: string) => request.post<BackendUser>(`/users/${id}/disable`)

export const enableUserApi = (id: string) => request.post<BackendUser>(`/users/${id}/enable`)

export const getSystemStatusApi = () => request.get<SystemStatus>('/system/status')

export const getSystemStatisticsApi = () => request.get<SystemStatistics>('/system/statistics')

export const getSystemInfoApi = () => request.get<Record<string, unknown>>('/system/info')
