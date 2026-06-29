import type { UserRole } from '@/types'

export function hasRole(userRoles: UserRole[], required?: UserRole[]): boolean {
  if (!required?.length) return true
  if (userRoles.includes('admin')) return true
  return required.some((r) => userRoles.includes(r))
}
