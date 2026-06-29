<template>
  <PageFrame :title="title" :description="description" :code="code">
    <slot />
  </PageFrame>
</template>

<script setup lang="ts">
import PageFrame from '@/components/PageFrame.vue'

defineProps<{
  title: string
  description?: string
  code?: string
}>()
</script>
