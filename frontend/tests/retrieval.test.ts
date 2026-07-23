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
