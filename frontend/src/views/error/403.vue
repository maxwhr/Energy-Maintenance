<template>
  <main class="grid min-h-[70vh] place-items-center">
    <div class="max-w-md rounded-md border border-red-400/30 bg-red-500/10 p-8 text-center">
      <div class="font-mono text-sm text-red-200">403 / 无权访问</div>
      <h1 class="mt-3 text-3xl font-black text-white">无权访问此页面</h1>
      <p class="mt-3 text-sm text-slate-300">当前角色没有对应功能权限，请返回运行总览或联系管理员调整角色。</p>
      <RouterLink class="scada-button primary mt-6" to="/dashboard">返回运行总览</RouterLink>
    </div>
  </main>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>
