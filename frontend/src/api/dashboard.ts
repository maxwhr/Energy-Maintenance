import request from '@/utils/request'
import type {
  DeviceStatistics,
  KnowledgeDocument,
  MaintenanceTask,
  PageResponse,
  RecordCenterOverview,
  SystemStatistics
} from '@/types'

export async function getDashboardStatsApi() {
  const [system, recordOverview, deviceStats, taskStats, tasks, documents] = await Promise.all([
    request.get<SystemStatistics>('/system/statistics'),
    request.get<RecordCenterOverview>('/record-center/overview'),
    request.get<DeviceStatistics>('/devices/statistics/summary'),
    request.get<Record<string, number>>('/maintenance/tasks/statistics/summary'),
    request.get<PageResponse<MaintenanceTask>>('/maintenance/tasks', { params: { page: 1, page_size: 5 } }),
    request.get<PageResponse<KnowledgeDocument>>('/knowledge/documents', { params: { page: 1, page_size: 5 } })
  ])
  return {
    system,
    recordOverview,
    deviceStats,
    taskStats,
    recentTasks: tasks.items,
    recentDocuments: documents.items
  }
}
