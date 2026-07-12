<template>
  <main class="auth-login-page" :style="{ backgroundImage: `url(${solarField})` }">
    <div class="auth-login-shade"></div>
    <header class="auth-login-nav">
      <RouterLink class="auth-login-brand" to="/login"><span>EM</span><div><strong>Energy-Maintenance</strong><small>光伏逆变器检修工作台</small></div></RouterLink>
      <RouterLink class="return-link" to="/login"><ArrowLeft :size="16" /> 返回介绍页</RouterLink>
    </header>
    <section class="auth-login-intro">
      <p>AUTHORIZED ACCESS</p><h1>进入专业、可信的<br />逆变器检修工作台</h1>
      <div></div><span>连接知识检索、来源追溯、辅助诊断与检修任务闭环。</span>
    </section>
    <form class="auth-login-card" @submit.prevent="submit">
      <div class="card-head"><p>身份认证</p><h2>欢迎回来</h2><span>使用管理员分配的系统账号登录</span></div>
      <label><span>{{ TEXT.loginPage.account }}</span><input v-model.trim="form.username" autocomplete="username" placeholder="请输入用户名" /></label>
      <label><span>{{ TEXT.loginPage.password }}</span><input v-model="form.password" type="password" autocomplete="current-password" placeholder="请输入密码" /></label>
      <p v-if="error" class="auth-error">{{ error }}</p>
      <button type="submit" :disabled="loading"><LogIn :size="18" />{{ loading ? '认证中' : '进入系统' }}</button>
      <div class="card-foot"><span>账号由系统管理员统一创建</span><RouterLink to="/login#account-guide">查看账号说明</RouterLink></div>
    </form>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ArrowLeft, LogIn } from '@lucide/vue'
import { useRoute, useRouter } from 'vue-router'
import { loginApi } from '@/api'
import { TEXT } from '@/constants/text'
import { useUserStore } from '@/stores/user'
import solarField from '@/assets/auth/solar-field.png'

const route=useRoute();const router=useRouter();const userStore=useUserStore();const loading=ref(false);const error=ref('');const form=reactive({username:'',password:''})
async function submit(){error.value='';if(!form.username)return void(error.value=TEXT.loginPage.accountRequired);if(!form.password)return void(error.value=TEXT.loginPage.passwordRequired);loading.value=true;try{const result=await loginApi(form);userStore.setAuth(result.token,result.user);await router.push((route.query.redirect as string)||'/dashboard')}catch(err){error.value=err instanceof Error?err.message:TEXT.loginPage.wrongCredential}finally{loading.value=false}}
</script>

<style scoped>
.auth-login-page{position:relative;min-height:100vh;display:grid;grid-template-columns:minmax(0,1fr) minmax(420px,560px);align-items:center;gap:clamp(50px,8vw,140px);padding:110px clamp(24px,8vw,140px) 70px;background-size:108% auto;background-position:center;background-repeat:no-repeat;color:#fff}.auth-login-shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,17,30,.95),rgba(3,17,30,.68) 52%,rgba(3,17,30,.35))}.auth-login-nav{position:absolute;z-index:2;inset:0 0 auto;height:76px;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(20px,4vw,72px);border-bottom:1px solid rgba(255,255,255,.16);background:rgba(4,18,31,.45);backdrop-filter:blur(12px)}.auth-login-brand{display:flex;align-items:center;gap:12px}.auth-login-brand>span{display:grid;width:42px;height:42px;place-items:center;background:#176cac;font-weight:900}.auth-login-brand strong,.auth-login-brand small{display:block}.auth-login-brand small{margin-top:2px;color:#aec4d3;font-size:11px}.return-link{display:flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.55);padding:10px 16px;font-size:13px;font-weight:900}.auth-login-intro,.auth-login-card{position:relative;z-index:1}.auth-login-intro{max-width:720px}.auth-login-intro>p{color:#69c7ee;font-size:12px;font-weight:900;letter-spacing:.18em}.auth-login-intro h1{margin-top:20px;font-size:clamp(46px,5vw,76px);line-height:1.08;font-weight:900;letter-spacing:-.04em;text-wrap:balance}.auth-login-intro>div{width:62px;height:3px;margin-top:28px;background:#62c2e9}.auth-login-intro>span{display:block;max-width:620px;margin-top:24px;color:#cbdde9;font-size:16px;line-height:1.85}.auth-login-card{display:grid;gap:20px;padding:40px;background:rgba(255,255,255,.97);border-top:3px solid #5dc2eb;color:#173047;box-shadow:0 32px 90px rgba(0,0,0,.36)}.card-head>p{color:#176cac;font-size:11px;font-weight:900;letter-spacing:.16em}.card-head h2{margin-top:7px;font-size:31px;font-weight:900}.card-head>span{display:block;margin-top:5px;color:#718798;font-size:13px}.auth-login-card label>span{display:block;margin-bottom:8px;font-size:13px;font-weight:900}.auth-login-card input{width:100%;border:1px solid #c8d6e0;padding:14px;outline:none}.auth-login-card input:focus{border-color:#176cac;box-shadow:0 0 0 3px rgba(23,108,172,.12)}.auth-login-card>button{display:flex;min-height:52px;align-items:center;justify-content:center;gap:9px;background:#176cac;color:#fff;font-weight:900}.auth-login-card>button:disabled{opacity:.55}.auth-error{border-left:3px solid #cf3f42;background:#fff0f0;padding:10px 12px;color:#a7262a}.card-foot{display:flex;justify-content:space-between;gap:14px;color:#718798;font-size:11px}.card-foot a{color:#176cac;font-weight:900}@media(max-width:900px){.auth-login-page{grid-template-columns:1fr;background-size:auto 108%}.auth-login-intro{padding-top:50px}.auth-login-card{max-width:620px;width:100%}}@media(max-width:600px){.auth-login-page{padding:100px 18px 36px}.auth-login-brand small{display:none}.auth-login-intro h1{font-size:44px}.auth-login-card{padding:24px}.card-foot{flex-direction:column}}
</style>
