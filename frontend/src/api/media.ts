import request from '@/utils/request'
import type { MediaOCRResult, MediaUploadResult, OCRStatusResult, PageResponse, UploadedMediaItem } from '@/types'

export const uploadMediaApi = (formData: FormData) =>
  request.post<MediaUploadResult>('/media/upload', formData)

export const getMediaApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<UploadedMediaItem>>('/media', { params })

export const getMediaDetailApi = (id: string) =>
  request.get<UploadedMediaItem>(`/media/${id}`)

export const getMediaContentApi = (id: string) =>
  request.get<Blob>(`/media/${id}/content`, { responseType: 'blob' })

export const getOCRStatusApi = () =>
  request.get<OCRStatusResult>('/media/ocr/status')

export const runMediaOCRApi = (id: string) =>
  request.post<MediaOCRResult>(`/media/${id}/ocr`)

export const getMediaOCRApi = (id: string) =>
  request.get<MediaOCRResult>(`/media/${id}/ocr`)
