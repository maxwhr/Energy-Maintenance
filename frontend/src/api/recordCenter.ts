import request from '@/utils/request'
import type {
  DeviceTimelineResponse,
  PageResponse,
  RecordCenterDetail,
  RecordCenterItem,
  RecordCenterOverview
} from '@/types'

export const getRecordCenterOverviewApi = (signal?: AbortSignal) =>
  request.get<RecordCenterOverview>('/record-center/overview', { signal })

export const searchRecordCenterApi = (params?: Record<string, unknown>, signal?: AbortSignal) =>
  request.get<PageResponse<RecordCenterItem>>('/record-center/search', { params, signal })

export const getRecordDetailApi = (recordType: string, recordId: string) =>
  request.get<RecordCenterDetail>(`/record-center/records/${recordType}/${recordId}`)

export const getDeviceTimelineApi = (deviceId: string) =>
  request.get<DeviceTimelineResponse>(`/record-center/devices/${deviceId}/timeline`)
