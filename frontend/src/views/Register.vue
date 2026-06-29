<template>
  <div class="auth-portal min-h-screen bg-[#f6f9fc] text-[#1f2d3d]">
    <header class="fixed inset-x-0 top-0 z-50 border-b border-[#dbe7f3] bg-white/92 shadow-sm backdrop-blur">
      <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
        <RouterLink class="flex items-center gap-3 text-left" to="/login">
          <span class="grid h-10 w-10 place-items-center rounded-md bg-[#195FA8] text-sm font-black text-white">EM</span>
          <span>
            <span class="block text-sm font-black text-[#1f2d3d]">Energy-Maintenance</span>
            <span class="block text-[11px] text-[#4f6f8f]">光伏逆变器检修工作台</span>
          </span>
        </RouterLink>
        <RouterLink class="auth-action-button" to="/login">返回登录</RouterLink>
      </div>
    </header>

    <main class="synoptic-grid flex min-h-screen items-center justify-center bg-[#eef6ff] px-5 pt-16">
      <section class="grid w-full max-w-5xl gap-6 lg:grid-cols-[1fr_0.9fr]">
        <div class="rounded-lg border border-[#dbe7f3] bg-white/94 p-8 shadow-[0_10px_30px_rgba(25,95,168,0.08)]">
          <p class="text-sm font-bold text-[#195FA8]">账号申请说明</p>
          <h1 class="mt-3 text-3xl font-black text-[#172538]">账号由管理员在后端统一创建</h1>
          <p class="mt-4 text-sm leading-7 text-[#53697f]">
            当前版本不开放公网自助注册，避免前端绕过后端权限与审计流程。请联系系统管理员创建账号，并分配管理员、专家、工程师或只读用户角色。
          </p>
          <div class="mt-6 grid gap-3 sm:grid-cols-2">
            <div v-for="item in roleCards" :key="item.role" class="rounded-md border border-[#dbe7f3] bg-[#f8fbfe] p-4">
              <div class="font-black text-[#172538]">{{ item.role }}</div>
              <p class="mt-2 text-sm leading-6 text-[#53697f]">{{ item.desc }}</p>
            </div>
          </div>
          <RouterLink class="scada-button primary mt-6" to="/login">使用已分配账号登录</RouterLink>
        </div>

        <div class="rounded-lg border border-[#cfe2f3] bg-white/88 p-6">
          <div class="mb-5 inline-flex items-center gap-2 rounded-md border border-[#8fc5e8] bg-white/78 px-3 py-2 font-mono text-xs font-bold text-[#195FA8]">
            <span class="status-dot text-[#23A55A]"></span>
            华为 / 阳光电源
          </div>
          <h2 class="text-2xl font-black text-[#172538]">第一版业务范围</h2>
          <ul class="mt-5 space-y-3 text-sm leading-7 text-[#53697f]">
            <li>支持厂家：华为、阳光电源。</li>
            <li>设备类型：pv_inverter，光伏逆变器。</li>
            <li>产品系列：SUN2000、FusionSolar、SG。</li>
            <li>核心工作：文档入库、检修问答、来源追溯、故障诊断和任务闭环。</li>
          </ul>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

const roleCards = [
  { role: '管理员', desc: '维护账号、系统状态、模型服务配置和权限策略。' },
  { role: '专家', desc: '审核知识资料，参与检修经验沉淀与纠错。' },
  { role: '工程师', desc: '上传资料、执行检修问答、诊断和任务处理。' },
  { role: '只读用户', desc: '查看运行总览和已授权的追溯信息。' }
]
</script>
