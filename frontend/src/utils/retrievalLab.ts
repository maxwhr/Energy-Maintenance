export function isRetrievalLabEnabled(status: Record<string, unknown> | null | undefined) {
  return status?.lab_enabled === true
}
