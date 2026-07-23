import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestMock = vi.hoisted(() => ({
  post: vi.fn(),
  get: vi.fn()
}))

vi.mock('@/utils/request', () => ({
  default: requestMock
}))

import { queryRetrievalApi } from '@/api/retrieval'
import type { RetrievalQueryRequest } from '@/types'
import { isRetrievalLabEnabled } from '@/utils/retrievalLab'

describe('retrieval request scope', () => {
  beforeEach(() => {
    requestMock.post.mockResolvedValue({ references: [] })
  })

  it.each([
    ['huawei', 'SUN2000', 'SUN2000 insulation resistance'],
    ['sungrow', 'SG', 'Sungrow SG inverter alarm']
  ])(
    'passes %s manufacturer and product series without rewriting',
    async (manufacturer, productSeries, question) => {
      const payload = {
        question,
        manufacturer,
        product_series: productSeries,
        persist_result: false,
        enable_llm: false,
        allow_real_api: false,
        enable_vector: false
      } as RetrievalQueryRequest
      await queryRetrievalApi(payload)
      expect(requestMock.post).toHaveBeenCalledWith('/retrieval/query', payload)
    }
  )
})

describe('retrieval lab visibility', () => {
  it('keeps the lab hidden when production status disables it', () => {
    expect(isRetrievalLabEnabled({ lab_enabled: false })).toBe(false)
    expect(isRetrievalLabEnabled(undefined)).toBe(false)
  })

  it('shows the lab only when the backend explicitly enables it', () => {
    expect(isRetrievalLabEnabled({ lab_enabled: true })).toBe(true)
  })
})
