import axios, { type AxiosRequestConfig } from 'axios'
import { TEXT } from '@/constants/text'
import type { ApiResponse } from '@/types'

const TOKEN_KEY = 'energy_maintenance_access_token'

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem('user_info')
}

export function showToast(message: string, type: 'info' | 'error' = 'info') {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { type, message } }))
}

const service = axios.create({
  baseURL: '/api',
  timeout: 15000
})

service.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

service.interceptors.response.use(
  (res) => {
    const body = res.data as ApiResponse
    if (!body || typeof body.code !== 'number') {
      return res.data
    }
    if (body.code === 0 || body.code === 200) {
      return body.data
    }
    const message = body.message || body.msg || TEXT.request.fail
    showToast(message, 'error')
    return Promise.reject(new Error(message))
  },
  (err) => {
    const status = err.response?.status
    const data = err.response?.data as Partial<ApiResponse> | undefined
    if (status === 401) {
      clearStoredToken()
      showToast(TEXT.request.authExpired, 'error')
      if (location.pathname !== '/login') {
        location.href = `/login?redirect=${encodeURIComponent(location.pathname + location.search)}`
      }
      return Promise.reject(new Error(TEXT.request.authExpired))
    } else if (status === 403) {
      showToast(TEXT.request.forbidden, 'error')
      return Promise.reject(new Error(TEXT.request.forbidden))
    }
    const message = normalizeRequestError(err, status, data)
    showToast(message, 'error')
    return Promise.reject(new Error(message))
  }
)

function normalizeRequestError(
  err: { code?: string; message?: string },
  status?: number,
  data?: Partial<ApiResponse>
) {
  if (status === 404) return '请求的资源不存在'
  if (status === 422) return '提交内容格式不正确，请检查后重试'
  if (status && status >= 500) return TEXT.request.serverError
  if (err.code === 'ECONNABORTED' || err.message?.toLowerCase().includes('timeout')) {
    return '请求超时，请稍后重试'
  }
  if (err.code === 'ERR_NETWORK' || err.message?.toLowerCase() === 'network error') {
    return '无法连接后端服务，请检查服务状态'
  }
  return data?.message || data?.msg || err.message || TEXT.request.serverError
}

const request = {
  get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.get(url, config) as Promise<T>
  },
  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return service.post(url, data, config) as Promise<T>
  },
  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    return service.put(url, data, config) as Promise<T>
  },
  delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    return service.delete(url, config) as Promise<T>
  }
}

export default request
