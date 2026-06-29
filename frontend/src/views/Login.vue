<template>
  <div class="auth-portal min-h-screen bg-[#f6f9fc] text-[#1f2d3d]">
    <header class="fixed inset-x-0 top-0 z-50 border-b border-[#dbe7f3] bg-white/92 shadow-sm backdrop-blur">
      <div class="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
        <button class="flex items-center gap-3 text-left" type="button" @click="scrollToHome">
          <span class="grid h-10 w-10 place-items-center rounded-md bg-[#195FA8] text-sm font-black text-white">EM</span>
          <span>
            <span class="block text-sm font-black text-[#1f2d3d]">Energy-Maintenance</span>
            <span class="block text-[11px] text-[#4f6f8f]">光伏逆变器检修工作台</span>
          </span>
        </button>

        <nav class="hidden items-center gap-1 rounded-md border border-[#dbe7f3] bg-[#f3f7fb] p-1 text-sm font-bold text-[#49647f] md:flex">
          <button class="auth-nav-link" type="button" @click="scrollToHome">首页</button>
          <RouterLink class="auth-nav-link active" to="/login">登录</RouterLink>
          <RouterLink class="auth-nav-link" to="/register">账号说明</RouterLink>
          <button class="auth-nav-link" type="button" @click="scrollToAbout">范围</button>
        </nav>

        <RouterLink class="auth-action-button" to="/register">账号申请说明</RouterLink>
      </div>
    </header>

    <main>
      <section id="home" class="synoptic-grid grid grid-cols-1 bg-[#eef6ff] pt-16 lg:grid-cols-[1.15fr_0.85fr]">
        <section class="relative flex min-h-[calc(100vh-4rem)] items-center justify-center overflow-hidden p-6">
          <div class="absolute inset-0 bg-[radial-gradient(circle_at_24%_18%,rgba(25,95,168,0.16),transparent_34%),radial-gradient(circle_at_78%_74%,rgba(35,165,90,0.12),transparent_32%)]"></div>
          <div class="relative w-full max-w-3xl">
            <div class="mb-5 inline-flex items-center gap-2 rounded-md border border-[#8fc5e8] bg-white/78 px-3 py-2 font-mono text-xs font-bold text-[#195FA8]">
              <span class="status-dot text-[#23A55A]"></span>
              华为 / 阳光电源 光伏逆变器
            </div>
            <h1 class="max-w-3xl text-4xl font-black leading-tight tracking-normal text-[#172538] sm:text-5xl">
              Energy-Maintenance
              <span class="block text-[#195FA8]">光伏逆变器检修工作台</span>
            </h1>
            <p class="mt-4 max-w-2xl text-base leading-7 text-[#4d6278]">
              面向华为 SUN2000 / FusionSolar 与阳光电源 SG 系列光伏逆变器，提供知识检索、来源追溯、故障诊断与检修任务闭环。
            </p>
            <div class="mt-8 rounded-md border border-[#c9d8e8] bg-white/88 p-4 shadow-[0_8px_24px_rgba(25,95,168,0.08)]">
              <svg viewBox="0 0 680 220" class="h-auto w-full" role="img" aria-label="光伏逆变器检修工作台预览">
                <rect x="10" y="10" width="660" height="200" rx="4" fill="#f8fbfe" stroke="#cbd9e7" />
                <path d="M70 110H610" stroke="#8fb0cf" stroke-width="8" stroke-linecap="round" />
                <g v-for="node in nodes" :key="node.name">
                  <rect :x="node.x" :y="node.y" width="128" height="48" rx="4" :fill="node.fill" :stroke="node.stroke" stroke-width="2" />
                  <text :x="node.x + 12" :y="node.y + 20" fill="#172538" font-size="13" font-weight="700">{{ node.name }}</text>
                  <text :x="node.x + 12" :y="node.y + 38" :fill="node.stroke" font-size="12">{{ node.value }}</text>
                </g>
              </svg>
            </div>
          </div>
        </section>

        <section class="relative flex min-h-[calc(100vh-4rem)] items-center justify-center p-6">
          <form class="relative w-full max-w-md space-y-5 rounded-lg border border-[#dbe7f3] bg-white/96 p-6 shadow-[0_10px_30px_rgba(25,95,168,0.08)]" @submit.prevent="submit">
            <div class="flex items-center justify-between">
              <div>
                <div class="text-sm font-bold text-[#195FA8]">身份认证</div>
                <h2 class="mt-2 text-2xl font-black text-[#172538]">进入检修工作台</h2>
              </div>
              <button type="button" class="text-sm font-bold text-[#195FA8] transition-colors hover:text-[#0F3A6B]" @click="goToRegister">
                账号说明
              </button>
            </div>
            <label class="block">
              <span class="mb-2 block text-sm font-bold text-[#33485f]">{{ TEXT.loginPage.account }}</span>
              <input v-model.trim="form.username" class="scada-input" autocomplete="username" />
            </label>
            <label class="block">
              <span class="mb-2 block text-sm font-bold text-[#33485f]">{{ TEXT.loginPage.password }}</span>
              <input v-model="form.password" class="scada-input" type="password" autocomplete="current-password" />
            </label>
            <p v-if="error" class="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ error }}</p>
            <button class="scada-button primary w-full" type="submit" :disabled="loading">
              <LogIn :size="18" />
              {{ loading ? '认证中' : TEXT.loginPage.btn }}
            </button>
            <p class="text-xs leading-6 text-[#64788f]">{{ TEXT.loginPage.accountTip }}</p>
          </form>
        </section>
      </section>

      <section id="about" class="border-y border-[#dbe7f3] bg-[#f8fbfe]">
        <div class="mx-auto grid max-w-7xl gap-6 px-5 py-16 md:grid-cols-3 lg:px-8">
          <div class="rounded-md border border-[#cfe2f3] bg-white p-5">
            <div class="text-lg font-black text-[#195FA8]">厂家范围</div>
            <p class="mt-3 text-sm leading-7 text-[#53697f]">第一版仅支持华为与阳光电源光伏逆变器检修场景。</p>
          </div>
          <div class="rounded-md border border-[#cdebd9] bg-white p-5">
            <div class="text-lg font-black text-[#1b874c]">知识追溯</div>
            <p class="mt-3 text-sm leading-7 text-[#53697f]">检修问答必须基于已入库文档切片返回真实来源。</p>
          </div>
          <div class="rounded-md border border-[#ffe0c2] bg-white p-5">
            <div class="text-lg font-black text-[#c76013]">国产化部署</div>
            <p class="mt-3 text-sm leading-7 text-[#53697f]">部署路线为 LoongArch、Kylin、Python 虚拟环境、PostgreSQL、systemd 与 Nginx。</p>
          </div>
        </div>
      </section>
    </main>
    <AppToast />
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { LogIn } from '@lucide/vue'
import AppToast from '@/components/AppToast.vue'
import { loginApi } from '@/api'
import { useUserStore } from '@/stores/user'
import { TEXT } from '@/constants/text'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const error = ref('')
const form = reactive({ username: '', password: '' })

const nodes = [
  { name: 'SUN2000', value: '华为', x: 72, y: 42, stroke: '#195fa8', fill: '#eef6ff' },
  { name: 'FusionSolar', value: '运维平台', x: 272, y: 42, stroke: '#23a55a', fill: '#eefaf3' },
  { name: 'SG 系列', value: '阳光电源', x: 472, y: 42, stroke: '#c76013', fill: '#fff7ed' },
  { name: '来源追溯', value: '参考资料', x: 272, y: 132, stroke: '#7c3aed', fill: '#f5f3ff' }
]

async function submit() {
  error.value = ''
  if (!form.username) {
    error.value = TEXT.loginPage.accountRequired
    return
  }
  if (!form.password) {
    error.value = TEXT.loginPage.passwordRequired
    return
  }
  loading.value = true
  try {
    const result = await loginApi(form)
    userStore.setAuth(result.token, result.user)
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: TEXT.loginPage.success } }))
    await router.push((route.query.redirect as string) || '/dashboard')
  } catch (err) {
    error.value = err instanceof Error ? err.message : TEXT.loginPage.wrongCredential
  } finally {
    loading.value = false
  }
}

function goToRegister() {
  router.push('/register')
}

function scrollToHome() {
  document.querySelector('#home')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function scrollToAbout() {
  document.querySelector('#about')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>
