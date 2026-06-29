<template>
  <div class="rounded-md border border-slate-600/20 bg-black/10 px-4 py-6 text-center text-sm text-slate-400">
    {{ text }}
  </div>
</template>

<script setup lang="ts">
defineProps<{
  text: string
}>()
</script>
