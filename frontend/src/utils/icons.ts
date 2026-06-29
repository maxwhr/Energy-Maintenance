import type { Component } from 'vue'
import { Circle } from '@lucide/vue'

export function resolveMenuIcon(icon?: Component) {
  return icon ?? Circle
}
