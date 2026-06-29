import request from '@/utils/request'
import type { BackendUser, LoginResult, UserInfo } from '@/types'
import { formatUserDisplayName } from '@/utils/display'

interface LoginResponseData {
  access_token: string
  token_type: string
  expires_in: number
  user: BackendUser
}

export function normalizeUser(user: BackendUser): UserInfo {
  const role = (user.role || 'viewer') as UserInfo['role']
  return {
    id: user.id,
    username: user.username,
    displayName: formatUserDisplayName(user.display_name, user.username),
    role,
    roles: [role],
    status: user.status
  }
}

export async function loginApi(data: { username: string; password: string }): Promise<LoginResult> {
  const result = await request.post<LoginResponseData>('/auth/login', data)
  return {
    token: result.access_token,
    accessToken: result.access_token,
    tokenType: result.token_type,
    expiresIn: result.expires_in,
    user: normalizeUser(result.user)
  }
}

export async function getUserInfoApi(): Promise<UserInfo> {
  const user = await request.get<BackendUser>('/auth/me')
  return normalizeUser(user)
}

export const logoutApi = () => request.post<Record<string, never>>('/auth/logout')
