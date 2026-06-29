<template>
  <section class="min-w-0 space-y-4">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="mb-2 flex items-center gap-2 text-xs font-bold text-cyan-200/80">
          <span class="h-px w-8 bg-cyan-300/60"></span>
          <span>{{ displayCode }}</span>
          <span v-if="code && displayCode !== code" class="font-mono text-[10px] font-normal text-slate-500">{{ code }}</span>
        </div>
        <h1 class="text-2xl font-black tracking-normal text-white">{{ title }}</h1>
        <p v-if="description" class="mt-1 max-w-3xl text-sm text-slate-300">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
        <slot name="actions" />
      </div>
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatPageCode } from '@/utils/display'

const props = defineProps<{
  title: string
  description?: string
  code?: string
}>()

const displayCode = computed(() => formatPageCode(props.code))
</script>
