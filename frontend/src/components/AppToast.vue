<template>
  <div class="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(360px,calc(100vw-32px))] flex-col gap-2">
    <transition-group name="toast">
      <div
        v-for="toast in toasts"
        :key="toast.id"
        class="pointer-events-auto rounded-md border px-4 py-3 text-sm shadow-lg"
        :class="toast.type === 'error'
          ? 'border-red-400/40 bg-red-950/90 text-red-50'
          : 'border-cyan-300/40 bg-slate-950/90 text-cyan-50'"
      >
        {{ toast.message }}
      </div>
    </transition-group>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'

interface ToastItem {
  id: number
  type: 'info' | 'error'
  message: string
}

const toasts = ref<ToastItem[]>([])
let seed = 0

function pushToast(event: Event) {
  const detail = (event as CustomEvent<{ type?: 'info' | 'error'; message?: string }>).detail
  if (!detail?.message) return
  const item = { id: ++seed, type: detail.type ?? 'info', message: detail.message }
  toasts.value.push(item)
  window.setTimeout(() => {
    toasts.value = toasts.value.filter((toast) => toast.id !== item.id)
  }, 2600)
}

onMounted(() => window.addEventListener('app:toast', pushToast))
onBeforeUnmount(() => window.removeEventListener('app:toast', pushToast))
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: opacity 160ms ease, transform 160ms ease;
}

.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}
</style>
