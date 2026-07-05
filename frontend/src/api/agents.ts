import request from '@/utils/request'
import type {
  AgentApproval,
  AgentArtifactConversionRequest,
  AgentArtifactConversionResult,
  AgentArtifactConversionStatus,
  AgentArtifact,
  AgentDefinition,
  AgentEventLog,
  AgentPage,
  AgentRun,
  AgentRunCreatePayload,
  AgentRunDetail,
  AgentRunTimeline,
  AgentStep,
  AgentToolExecutePayload,
  AgentToolExecuteResult,
  AgentTool,
  AgentToolCall
} from '@/types/agent'

export const getAgentDefinitions = (params?: Record<string, unknown>) =>
  request.get<AgentDefinition[]>('/agents/definitions', { params })

export const getAgentDefinition = (agentCode: string) =>
  request.get<AgentDefinition>(`/agents/definitions/${agentCode}`)

export const getAgentTools = (params?: Record<string, unknown>) =>
  request.get<AgentTool[]>('/agents/tools', { params })

export const createAgentRun = (data: AgentRunCreatePayload) =>
  request.post<AgentRun>('/agents/runs', data)

export const getAgentRuns = (params?: Record<string, unknown>) =>
  request.get<AgentPage<AgentRun>>('/agents/runs', { params })

export const getAgentRunDetail = (runId: string) =>
  request.get<AgentRunDetail>(`/agents/runs/${runId}`)

export const getAgentRunTimeline = (runId: string) =>
  request.get<AgentRunTimeline>(`/agents/runs/${runId}/timeline`)

export const cancelAgentRun = (runId: string) =>
  request.post<AgentRun>(`/agents/runs/${runId}/cancel`)

export const executeAgentRunTool = (runId: string, data: AgentToolExecutePayload) =>
  request.post<AgentToolExecuteResult>(`/agents/runs/${runId}/execute-tool`, data)

export const getAgentRunSteps = (runId: string) =>
  request.get<AgentStep[]>(`/agents/runs/${runId}/steps`)

export const getAgentRunToolCalls = (runId: string) =>
  request.get<AgentToolCall[]>(`/agents/runs/${runId}/tool-calls`)

export const getAgentRunApprovals = (runId: string) =>
  request.get<AgentApproval[]>(`/agents/runs/${runId}/approvals`)

export const approveAgentApproval = (approvalId: string, review_comment?: string) =>
  request.post<AgentApproval>(`/agents/approvals/${approvalId}/approve`, { review_comment })

export const rejectAgentApproval = (approvalId: string, review_comment?: string) =>
  request.post<AgentApproval>(`/agents/approvals/${approvalId}/reject`, { review_comment })

export const getAgentArtifacts = (runId: string) =>
  request.get<AgentArtifact[]>(`/agents/runs/${runId}/artifacts`)

export const getAgentEvents = (params?: Record<string, unknown>) =>
  request.get<AgentPage<AgentEventLog>>('/agents/events', { params })

export const getAgentArtifactConversionStatus = (artifactId: string) =>
  request.get<AgentArtifactConversionStatus>(`/agents/artifacts/${artifactId}/conversion-status`)

export const convertAgentArtifact = (artifactId: string, data: AgentArtifactConversionRequest) =>
  request.post<AgentArtifactConversionResult>(`/agents/artifacts/${artifactId}/convert`, data)

export const getAgentArtifactConversions = (params?: Record<string, unknown>) =>
  request.get<AgentPage<AgentArtifactConversionResult>>('/agents/conversions', { params })

export const getAgentRunConversions = (runId: string) =>
  request.get<AgentArtifactConversionResult[]>(`/agents/runs/${runId}/conversions`)

export const getAgentArtifactConversionHistory = (artifactId: string) =>
  request.get<AgentArtifactConversionResult[]>(`/agents/artifacts/${artifactId}/conversions`)

export const getAgentArtifactConversion = (conversionTraceId: string) =>
  request.get<AgentArtifactConversionResult>(`/agents/conversions/${conversionTraceId}`)

export const getAgentArtifactConversionDetail = (conversionId: string) =>
  request.get<AgentArtifactConversionResult>(`/agents/conversions/${conversionId}/detail`)

export const voidAgentArtifactConversion = (conversionId: string, reason?: string) =>
  request.post<AgentArtifactConversionResult>(`/agents/conversions/${conversionId}/void`, { reason })
