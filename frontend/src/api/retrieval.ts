import request from '@/utils/request'
import { getStoredToken } from '@/utils/request'
import type { PageResponse, RetrievalResponse } from '@/types'

export const queryRetrievalApi = (data: Record<string, unknown>) =>
  request.post<RetrievalResponse>('/retrieval/query', data)

export const getRetrievalRecordsApi = (params?: Record<string, unknown>) =>
  request.get<PageResponse<Record<string, unknown>>>('/retrieval/records', { params })

export const getRetrievalRecordApi = (traceId: string) =>
  request.get<Record<string, unknown>>(`/retrieval/records/${traceId}`)

export interface RetrievalStreamEvent {
  type: 'retrieval' | 'delta' | 'done' | 'error' | string
  content?: string
  message?: string
  response?: RetrievalResponse
  model_call_trace_id?: string | null
  model_provider?: string | null
  model_name?: string | null
}

export async function streamRetrievalApi(
  data: Record<string, unknown>,
  onEvent: (event: RetrievalStreamEvent) => void
) {
  const token = getStoredToken()
  const response = await fetch('/api/retrieval/query/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: JSON.stringify(data)
  })
  if (!response.ok || !response.body) {
    throw new Error(`Stream request failed: HTTP ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split('\n\n')
    buffer = frames.pop() || ''
    for (const frame of frames) {
      const event = parseSseFrame(frame)
      if (event) onEvent(event)
    }
  }
  if (buffer.trim()) {
    const event = parseSseFrame(buffer)
    if (event) onEvent(event)
  }
}

function parseSseFrame(frame: string): RetrievalStreamEvent | null {
  const dataLines = frame
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
  if (!dataLines.length) return null
  try {
    return JSON.parse(dataLines.join('\n')) as RetrievalStreamEvent
  } catch {
    return null
  }
}
