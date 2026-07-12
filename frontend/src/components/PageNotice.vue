<template>
  <div class="page-notice flex items-start gap-3 rounded-lg border px-4 py-3 text-sm" :class="toneClass" role="status">
    <component :is="icon" class="mt-0.5 shrink-0" :size="17" />
    <div class="min-w-0 flex-1">
      <div v-if="title" class="font-black">{{ title }}</div>
      <div class="leading-6" :class="title ? 'mt-0.5' : ''">{{ message }}</div>
    </div>
    <button v-if="retry" class="shrink-0 font-black underline underline-offset-4" type="button" @click="$emit('retry')">重试</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { AlertTriangle, CircleCheck, Info, LoaderCircle } from '@lucide/vue'

const props = withDefaults(defineProps<{
  message: string
  title?: string
  tone?: 'info' | 'success' | 'warning' | 'error' | 'loading'
  retry?: boolean
}>(), { tone: 'info', retry: false })

defineEmits<{ retry: [] }>()

const icon = computed(() => ({
  success: CircleCheck,
  warning: AlertTriangle,
  error: AlertTriangle,
  loading: LoaderCircle,
  info: Info
})[props.tone])

const toneClass = computed(() => ({
  success: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-200',
  warning: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
  error: 'border-red-400/30 bg-red-500/10 text-red-200',
  loading: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-200',
  info: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-200'
})[props.tone])
</script>
