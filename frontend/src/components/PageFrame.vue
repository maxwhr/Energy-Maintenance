<template>
  <section class="page-frame min-w-0 space-y-5">
    <div class="page-heading flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <div class="mb-2 flex items-center gap-2 text-xs font-bold text-cyan-200/80">
          <span class="h-px w-8 bg-cyan-300/60"></span>
          <span>{{ displayCode }}</span>
          <span v-if="code && displayCode !== code" class="font-mono text-[10px] font-normal text-slate-500">{{ code }}</span>
        </div>
        <h1 class="text-2xl font-black tracking-normal text-white sm:text-[28px]">{{ title }}</h1>
        <p v-if="description" class="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{{ description }}</p>
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
