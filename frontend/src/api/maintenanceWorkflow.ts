import request from '@/utils/request'
import type {
  MaintenanceWorkflow,
  MaintenanceWorkflowPage,
  MaintenanceWorkflowStatus
} from '@/types/maintenanceWorkflow'

export const getMaintenanceWorkflows = (params?: Record<string, unknown>) =>
  request.get<MaintenanceWorkflowPage>('/maintenance-workflows', { params })

export const getMaintenanceWorkflow = (workflowId: string) =>
  request.get<MaintenanceWorkflow>(`/maintenance-workflows/${workflowId}`)

export const createMaintenanceWorkflow = (data: Record<string, unknown>) =>
  request.post<MaintenanceWorkflow>('/maintenance-workflows', data)

export const getMaintenanceWorkflowStatus = () =>
  request.get<MaintenanceWorkflowStatus>('/system/maintenance-workflow/status')

export const postWorkflowAction = <T = Record<string, any>>(
  workflowId: string,
  action: string,
  data: Record<string, unknown>
) => request.post<T>(`/maintenance-workflows/${workflowId}/${action}`, data)

export const updateWorkflowStep = (
  workflowId: string,
  stepId: string,
  data: Record<string, unknown>
) => request.post<Record<string, any>>(`/maintenance-workflows/${workflowId}/task/steps/${stepId}`, data)

