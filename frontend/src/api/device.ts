import request from '@/utils/request'
import type { DeviceItem, DeviceStatistics, PageResponse } from '@/types'

export const getDevicesApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<DeviceItem>>('/devices', { params })

export const createDeviceApi = (data: Record<string, unknown>) =>
  request.post<DeviceItem>('/devices', data)

export const getDeviceApi = (id: string) => request.get<DeviceItem>(`/devices/${id}`)

export const updateDeviceApi = (id: string, data: Record<string, unknown>) =>
  request.put<DeviceItem>(`/devices/${id}`, data)

export const retireDeviceApi = (id: string) => request.post<DeviceItem>(`/devices/${id}/retire`)

export const getDeviceMaintenanceRecordsApi = (id: string, params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>(`/devices/${id}/maintenance-records`, { params })

export const createDeviceMaintenanceRecordApi = (id: string, data: Record<string, unknown>) =>
  request.post<Record<string, unknown>>(`/devices/${id}/maintenance-records`, data)

export const getDeviceStatisticsApi = () => request.get<DeviceStatistics>('/devices/statistics/summary')
