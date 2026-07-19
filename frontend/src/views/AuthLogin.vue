<template>
  <main class="auth-login-page" :style="{ backgroundImage: `url(${solarField})` }">
    <div class="auth-login-shade"></div>
    <header class="auth-login-nav">
      <RouterLink class="auth-login-brand" to="/login" aria-label="返回 Energy-Maintenance 介绍首页">
        <span>EM</span>
        <div><strong>Energy-Maintenance</strong><small>华为 SUN2000 检修工作台</small></div>
      </RouterLink>
      <RouterLink class="return-link" to="/login"><ArrowLeft :size="16" /> 返回介绍页</RouterLink>
    </header>

    <section class="auth-login-intro">
      <p>AUTHORIZED ACCESS</p>
      <h1>进入专业、可信的<br />逆变器检修工作台</h1>
      <div></div>
      <span>连接知识检索、真实来源引用、辅助诊断、标准 SOP 与检修任务闭环。</span>
      <dl>
        <div><dt>正式知识范围</dt><dd>Huawei SUN2000</dd></div>
        <div><dt>安全边界</dt><dd>辅助建议与人工审核</dd></div>
      </dl>
    </section>

    <form class="auth-login-card" novalidate @submit.prevent="submit">
      <div class="card-head">
        <p>身份认证</p>
        <h2>欢迎回来</h2>
        <span>使用系统管理员分配的账号登录</span>
      </div>

      <label>
        <span>{{ TEXT.loginPage.account }}</span>
        <input v-model.trim="form.username" autocomplete="username" placeholder="请输入用户名" autofocus />
      </label>

      <label>
        <span>{{ TEXT.loginPage.password }}</span>
        <span class="password-field">
          <input
            v-model="form.password"
            :type="showPassword ? 'text' : 'password'"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
          <button
            type="button"
            :title="showPassword ? '隐藏密码' : '显示密码'"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
            @click="showPassword = !showPassword"
          >
            <EyeOff v-if="showPassword" :size="18" />
            <Eye v-else :size="18" />
          </button>
        </span>
      </label>

      <p v-if="error" class="auth-error" role="alert">{{ error }}</p>
      <button class="login-submit" type="submit" :disabled="loading">
        <LogIn :size="18" />
        {{ loading ? '认证中' : '进入系统' }}
      </button>
      <div class="card-foot">
        <span>账号由系统管理员统一创建</span>
        <RouterLink to="/register">查看账号说明</RouterLink>
      </div>
    </form>
    <AppToast />
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ArrowLeft, Eye, EyeOff, LogIn } from '@lucide/vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import AppToast from '@/components/AppToast.vue'
import { loginApi } from '@/api'
import { TEXT } from '@/constants/text'
import { useUserStore } from '@/stores/user'
import solarField from '@/assets/auth/solar-field.png'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const error = ref('')
const showPassword = ref(false)
const form = reactive({ username: '', password: '' })

function safeRedirect(value: unknown) {
  return typeof value === 'string' && value.startsWith('/') && !value.startsWith('//')
    ? value
    : '/dashboard'
}

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
    await router.push(safeRedirect(route.query.redirect))
  } catch (err) {
    error.value = err instanceof Error ? err.message : TEXT.loginPage.wrongCredential
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-login-page {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(420px, 540px);
  min-height: 100svh;
  align-items: center;
  gap: 8vw;
  overflow: hidden;
  padding: 110px 8vw 56px;
  background-position: center;
  background-size: cover;
  color: #fff;
}

.auth-login-shade { position: absolute; inset: 0; background: rgb(3 17 29 / 72%); }

.auth-login-nav {
  position: absolute;
  z-index: 2;
  inset: 0 0 auto;
  display: flex;
  height: 72px;
  align-items: center;
  justify-content: space-between;
  padding: 0 4vw;
  border-bottom: 1px solid rgb(255 255 255 / 18%);
  background: rgb(4 18 31 / 62%);
  backdrop-filter: blur(12px);
}

.auth-login-brand { display: flex; align-items: center; gap: 12px; }
.auth-login-brand > span { display: grid; width: 42px; height: 42px; place-items: center; background: #176cac; color: #fff; font-weight: 900; }
.auth-login-brand strong,
.auth-login-brand small { display: block; letter-spacing: 0; }
.auth-login-brand small { margin-top: 2px; color: #b5cad8; font-size: 11px; }
.return-link { display: flex; min-height: 40px; align-items: center; gap: 8px; border: 1px solid rgb(255 255 255 / 58%); padding: 0 15px; font-size: 13px; font-weight: 900; }
.return-link:hover,
.return-link:focus-visible { border-color: #69c8ee; background: #fff; color: #0b314c; outline: none; }

.auth-login-intro,
.auth-login-card { position: relative; z-index: 1; }
.auth-login-intro { max-width: 700px; }
.auth-login-intro > p { margin: 0; color: #69c8ee; font-size: 12px; font-weight: 900; }
.auth-login-intro h1 { margin: 19px 0 0; font-size: 58px; line-height: 1.1; letter-spacing: 0; text-wrap: balance; }
.auth-login-intro > div { width: 62px; height: 3px; margin-top: 26px; background: #69c8ee; }
.auth-login-intro > span { display: block; max-width: 600px; margin-top: 22px; color: #d1e1eb; font-size: 16px; line-height: 1.85; }
.auth-login-intro dl { display: grid; grid-template-columns: 1fr 1fr; max-width: 590px; margin: 30px 0 0; border-top: 1px solid rgb(255 255 255 / 30%); border-bottom: 1px solid rgb(255 255 255 / 30%); }
.auth-login-intro dl div { padding: 14px 16px 14px 0; }
.auth-login-intro dl div + div { padding-left: 16px; border-left: 1px solid rgb(255 255 255 / 24%); }
.auth-login-intro dt { color: #a4c0d0; font-size: 10px; font-weight: 800; }
.auth-login-intro dd { margin: 5px 0 0; font-size: 13px; font-weight: 900; }

.auth-login-card {
  display: grid;
  gap: 19px;
  border-top: 3px solid #69c8ee;
  background: rgb(255 255 255 / 97%);
  padding: 38px;
  color: #173047;
  box-shadow: 0 30px 80px rgb(0 0 0 / 34%);
}
.card-head > p { margin: 0; color: #176cac; font-size: 11px; font-weight: 900; }
.card-head h2 { margin: 7px 0 0; font-size: 30px; }
.card-head > span { display: block; margin-top: 5px; color: #718798; font-size: 12px; }
.auth-login-card label > span:first-child { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 900; }
.auth-login-card input { width: 100%; min-height: 48px; border: 1px solid #c8d6e0; background: #fff; padding: 0 13px; color: #173047; outline: none; }
.auth-login-card input:focus { border-color: #176cac; box-shadow: 0 0 0 3px rgb(23 108 172 / 13%); }
.password-field { position: relative; display: block; }
.password-field input { padding-right: 48px; }
.password-field button { position: absolute; top: 4px; right: 4px; display: grid; width: 40px; height: 40px; place-items: center; color: #5f7789; }
.password-field button:hover,
.password-field button:focus-visible { background: #edf5fa; color: #176cac; outline: none; }
.auth-error { margin: 0; border-left: 3px solid #cf3f42; background: #fff0f0; padding: 10px 12px; color: #a7262a; font-size: 13px; }
.login-submit { display: flex; min-height: 50px; align-items: center; justify-content: center; gap: 9px; background: #176cac; color: #fff; font-weight: 900; }
.login-submit:hover:not(:disabled),
.login-submit:focus-visible { background: #0d5488; outline: 3px solid rgb(23 108 172 / 24%); outline-offset: 3px; }
.card-foot { display: flex; justify-content: space-between; gap: 14px; color: #718798; font-size: 11px; }
.card-foot a { color: #176cac; font-weight: 900; }

@media (max-width: 940px) {
  .auth-login-page { grid-template-columns: 1fr; align-content: center; gap: 42px; background-position: 60% center; }
  .auth-login-intro { padding-top: 30px; }
  .auth-login-card { width: min(600px, 100%); }
}

@media (max-width: 600px) {
  .auth-login-page { padding: 96px 18px 32px; }
  .auth-login-nav { height: 66px; padding-inline: 18px; }
  .auth-login-brand small { display: none; }
  .return-link { padding-inline: 11px; }
  .auth-login-intro h1 { font-size: 40px; }
  .auth-login-intro > span { font-size: 14px; }
  .auth-login-intro dl { grid-template-columns: 1fr; }
  .auth-login-intro dl div + div { padding-left: 0; border-top: 1px solid rgb(255 255 255 / 22%); border-left: 0; }
  .auth-login-card { padding: 24px; }
  .card-foot { flex-direction: column; }
}

@media (prefers-reduced-motion: reduce) {
  .auth-login-page * { scroll-behavior: auto; transition: none; }
}
</style>
