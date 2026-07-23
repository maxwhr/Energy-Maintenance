import { beforeEach, describe, expect, it, vi } from 'vitest'

const axiosMock = vi.hoisted(() => {
  const handlers: {
    fulfilled?: (value: unknown) => unknown
    rejected?: (reason: unknown) => Promise<never>
  } = {}
  const service = {
    interceptors: {
      request: { use: vi.fn() },
      response: {
        use: vi.fn(
          (
            fulfilled: (value: unknown) => unknown,
            rejected: (reason: unknown) => Promise<never>
          ) => {
            handlers.fulfilled = fulfilled
            handlers.rejected = rejected
          }
        )
      }
    },
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
  return { handlers, service }
})

vi.mock('axios', () => ({
  default: {
    create: vi.fn(() => axiosMock.service),
    isCancel: vi.fn(() => false)
  }
}))

import {
  clearStoredToken,
  getStoredToken,
  setStoredToken
} from '@/utils/request'

describe('API response handling', () => {
  beforeEach(() => {
    localStorage.clear()
    history.replaceState({}, '', '/login')
  })

  it('clears token and user state after a 401 response', async () => {
    setStoredToken('expired-token')
    localStorage.setItem('user_info', '{"username":"viewer"}')
    await expect(
      axiosMock.handlers.rejected?.({ response: { status: 401, data: {} } })
    ).rejects.toBeInstanceOf(Error)
    expect(getStoredToken()).toBe('')
    expect(localStorage.getItem('user_info')).toBeNull()
  })

  it('unwraps a successful unified API response', () => {
    const result = axiosMock.handlers.fulfilled?.({
      data: { code: 0, message: 'success', data: { ok: true } }
    })
    expect(result).toEqual({ ok: true })
  })

  it('does not accept code 200 as a successful business response', async () => {
    await expect(
      axiosMock.handlers.fulfilled?.({
        data: { code: 200, message: 'legacy response rejected', data: null }
      })
    ).rejects.toThrow('legacy response rejected')
  })

  it('rejects a unified API business error', async () => {
    await expect(
      axiosMock.handlers.fulfilled?.({
        data: { code: 400, message: 'invalid request', data: null }
      })
    ).rejects.toThrow('invalid request')
  })

  it('clears stored credentials explicitly', () => {
    setStoredToken('temporary-token')
    localStorage.setItem('user_info', '{"username":"engineer"}')
    clearStoredToken()
    expect(getStoredToken()).toBe('')
    expect(localStorage.getItem('user_info')).toBeNull()
  })

  it('keeps the token after a 403 response', async () => {
    setStoredToken('active-token')
    await expect(
      axiosMock.handlers.rejected?.({
        response: {
          status: 403,
          data: { code: 40302, message: 'Permission denied', data: null }
        }
      })
    ).rejects.toThrow('Permission denied')
    expect(getStoredToken()).toBe('active-token')
  })

  it('uses the backend validation message for a 422 response', async () => {
    await expect(
      axiosMock.handlers.rejected?.({
        response: {
          status: 422,
          data: {
            code: 42200,
            message: 'Request validation failed: body.username required',
            data: null
          }
        }
      })
    ).rejects.toThrow('Request validation failed: body.username required')
  })
})
