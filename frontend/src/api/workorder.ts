import request from '@/utils/request'
import type { AssignableUser, MaintenanceTask, PageResponse } from '@/types'

export const getWorkordersApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<MaintenanceTask>>('/maintenance/tasks', { params })

export const getWorkorderApi = (id: string) =>
  request.get<Record<string, unknown>>(`/maintenance/tasks/${id}`)

export const createWorkorderApi = (data: Record<string, unknown>) =>
  request.post<MaintenanceTask>('/maintenance/tasks', data)

export const updateWorkorderApi = (id: string, data: Record<string, unknown>) =>
  request.put<MaintenanceTask>(`/maintenance/tasks/${id}`, data)

export const assignWorkorderApi = (id: string, assignee_id: string) =>
  request.post<MaintenanceTask>(`/maintenance/tasks/${id}/assign`, { assignee_id })

export const startWorkorderApi = (id: string) =>
  request.post<MaintenanceTask>(`/maintenance/tasks/${id}/start`)

export const completeWorkorderApi = (id: string, data: Record<string, unknown>) =>
  request.post<Record<string, unknown>>(`/maintenance/tasks/${id}/complete`, data)

export const cancelWorkorderApi = (id: string, reason: string) =>
  request.post<MaintenanceTask>(`/maintenance/tasks/${id}/cancel`, { reason })

export const getWorkorderStatisticsApi = () =>
  request.get<Record<string, number>>('/maintenance/tasks/statistics/summary')

export const getAssignableUsersApi = () =>
  request.get<AssignableUser[]>('/maintenance/tasks/assignable-users')
