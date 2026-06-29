import request from '@/utils/request'
import type {
  DeviceTimelineResponse,
  PageResponse,
  RecordCenterDetail,
  RecordCenterItem,
  RecordCenterOverview
} from '@/types'

export const getRecordCenterOverviewApi = () =>
  request.get<RecordCenterOverview>('/record-center/overview')

export const searchRecordCenterApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<RecordCenterItem>>('/record-center/search', { params })

export const getRecordDetailApi = (recordType: string, recordId: string) =>
  request.get<RecordCenterDetail>(`/record-center/records/${recordType}/${recordId}`)

export const getDeviceTimelineApi = (deviceId: string) =>
  request.get<DeviceTimelineResponse>(`/record-center/devices/${deviceId}/timeline`)
