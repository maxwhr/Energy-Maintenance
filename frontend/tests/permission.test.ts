import { describe, expect, it } from 'vitest'
import router from '@/router'
import { hasRole } from '@/utils/permission'
import type { UserRole } from '@/types'

function rolesFor(path: string): UserRole[] {
  const route = router.getRoutes().find((item) => item.path === path)
  return (route?.meta.roles ?? []) as UserRole[]
}

describe('route permissions', () => {
  it('allows admin to access administrator routes', () => {
    expect(hasRole(['admin'], rolesFor('/system/users'))).toBe(true)
  })

  it('denies viewer access to administrator routes', () => {
    expect(hasRole(['viewer'], rolesFor('/system/users'))).toBe(false)
  })

  it('allows viewer access to the knowledge graph', () => {
    expect(rolesFor('/knowledge/graph')).toContain('viewer')
    expect(hasRole(['viewer'], rolesFor('/knowledge/graph'))).toBe(true)
  })

  it.each(['admin', 'expert', 'engineer'] as UserRole[])(
    'allows %s to access operator routes',
    (role) => {
      expect(hasRole([role], rolesFor('/knowledge/search'))).toBe(true)
    }
  )
})
