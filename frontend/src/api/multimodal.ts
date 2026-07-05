import request from '@/utils/request'
import type { PageResponse } from '@/types'
import type {
  MediaAIAnalysis,
  MediaEvidenceLink,
  MediaEvidenceLinkPayload,
  MediaMultimodalSummary,
  MediaOCRResult,
  MediaProcessingJob,
  MediaProcessingJobPayload
} from '@/types/multimodal'

export const getMediaJobs = (mediaId: string, params?: Record<string, unknown>) =>
  request.get<PageResponse<MediaProcessingJob>>(`/multimodal/media/${mediaId}/jobs`, { params })

export const createMediaProcessingJob = (mediaId: string, data: MediaProcessingJobPayload) =>
  request.post<MediaProcessingJob>(`/multimodal/media/${mediaId}/jobs`, data)

export const getProcessingJob = (jobId: string) =>
  request.get<MediaProcessingJob>(`/multimodal/jobs/${jobId}`)

export const cancelProcessingJob = (jobId: string) =>
  request.post<MediaProcessingJob>(`/multimodal/jobs/${jobId}/cancel`)

export const getMediaOcrResults = (mediaId: string, params?: Record<string, unknown>) =>
  request.get<PageResponse<MediaOCRResult>>(`/multimodal/media/${mediaId}/ocr-results`, { params })

export const getOcrResult = (resultId: string) =>
  request.get<MediaOCRResult>(`/multimodal/ocr-results/${resultId}`)

export const getMediaAnalyses = (mediaId: string, params?: Record<string, unknown>) =>
  request.get<PageResponse<MediaAIAnalysis>>(`/multimodal/media/${mediaId}/analyses`, { params })

export const getAnalysis = (analysisId: string) =>
  request.get<MediaAIAnalysis>(`/multimodal/analyses/${analysisId}`)

export const reviewAnalysis = (
  analysisId: string,
  data: { human_review_status: 'pending' | 'accepted' | 'rejected' | 'revised'; review_comment?: string | null }
) => request.post<MediaAIAnalysis>(`/multimodal/analyses/${analysisId}/review`, data)

export const getEvidenceLinks = (params?: Record<string, unknown>) =>
  request.get<PageResponse<MediaEvidenceLink>>('/multimodal/evidence-links', { params })

export const createEvidenceLink = (data: MediaEvidenceLinkPayload) =>
  request.post<MediaEvidenceLink>('/multimodal/evidence-links', data)

export const getMediaMultimodalSummary = (mediaId: string) =>
  request.get<MediaMultimodalSummary>(`/multimodal/media/${mediaId}/summary`)
