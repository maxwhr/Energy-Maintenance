import { defineStore } from 'pinia'
import { getUserInfoApi, logoutApi } from '@/api/auth'
import { clearStoredToken, getStoredToken, setStoredToken } from '@/utils/request'
import { hasRole } from '@/utils/permission'
import type { UserInfo, UserRole } from '@/types'

const USER_KEY = 'user_info'

function loadUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? (JSON.parse(raw) as UserInfo) : null
  } catch {
    return null
  }
}

export const useUserStore = defineStore('user', {
  state: () => {
    const user = loadUser()
    return {
      token: getStoredToken(),
      user: user as UserInfo | null,
      restoring: false
    }
  },
  getters: {
    username: (s) => s.user?.username ?? '',
    displayName: (s) => s.user?.displayName ?? s.user?.username ?? '',
    role: (s): UserRole | undefined => s.user?.role,
    roles: (s): UserRole[] => s.user?.roles ?? [],
    isLoggedIn: (s) => !!s.token
  },
  actions: {
    setAuth(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      setStoredToken(token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    setUser(user: UserInfo) {
      this.user = user
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    },
    async restoreUser() {
      if (!this.token || this.user) return this.user
      if (this.restoring) return this.user
      this.restoring = true
      try {
        const user = await getUserInfoApi()
        this.setUser(user)
        return user
      } catch {
        this.clearAuth()
        return null
      } finally {
        this.restoring = false
      }
    },
    setDisplayName(name: string) {
      if (this.user) {
        this.user.displayName = name
        localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      }
    },
    updateUserInfo(info: Partial<UserInfo>) {
      if (this.user) {
        this.user = { ...this.user, ...info }
        localStorage.setItem(USER_KEY, JSON.stringify(this.user))
      }
    },
    async logout() {
      try {
        await logoutApi()
      } catch {
        // Logout should clear local session even when the backend is unavailable.
      }
      this.clearAuth()
    },
    clearAuth() {
      this.token = ''
      this.user = null
      clearStoredToken()
    },
    canAccess(required?: UserRole[]) {
      return hasRole(this.roles, required)
    }
  }
})
