<template>
  <div class="account-page" :style="{ backgroundImage: `url(${fieldEngineer})` }">
    <div class="account-overlay"></div>
    <header class="account-nav">
      <RouterLink class="account-brand" to="/login"><span>EM</span><div><strong>Energy-Maintenance</strong><small>光伏逆变器检修工作台</small></div></RouterLink>
      <RouterLink class="back-link" to="/login"><ArrowLeft :size="16" /> 返回登录</RouterLink>
    </header>
    <main class="account-content">
      <section class="account-intro">
        <p>ACCOUNT &amp; PERMISSION</p>
        <h1>以清晰权限<br />守护专业作业</h1>
        <div class="intro-line"></div>
        <p class="intro-copy">系统账号由管理员统一创建并分配角色，让知识审核、诊断操作、任务流转与审计记录始终处于清晰、可信的权限边界内。</p>
      </section>
      <section class="account-panel">
        <div class="panel-head"><p>账号申请说明</p><h2>当前版本不开放自助注册</h2><span>请联系系统管理员创建账号，并明确实际工作职责。</span></div>
        <div class="role-grid"><article v-for="(item,index) in roleCards" :key="item.role"><span>0{{ index+1 }}</span><div><strong>{{ item.role }}</strong><p>{{ item.desc }}</p></div></article></div>
        <div class="scope-note"><ShieldCheck :size="20" /><p><strong>权限与审计</strong><span>前端不会绕过后端权限。账号创建、角色分配和关键操作均以服务端校验为准。</span></p></div>
        <RouterLink class="account-action" to="/login">使用已分配账号登录 <ArrowRight :size="17" /></RouterLink>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, ArrowRight, ShieldCheck } from '@lucide/vue'
import fieldEngineer from '@/assets/auth/field-engineer.png'
const roleCards=[
  {role:'管理员',desc:'维护账号、系统状态、模型服务配置和权限策略。'},
  {role:'专家',desc:'审核知识资料，参与检修经验沉淀与人工纠错。'},
  {role:'工程师',desc:'执行知识检索、故障诊断、资料上传和任务处理。'},
  {role:'只读用户',desc:'查看已授权的运行总览、记录与追溯信息。'}
]
</script>

<style scoped>
.account-page{position:relative;min-height:100vh;background-size:cover;background-position:center;color:#fff}.account-overlay{position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,16,28,.94) 0%,rgba(3,16,28,.77) 45%,rgba(3,16,28,.2) 100%),linear-gradient(0deg,rgba(3,16,28,.45),transparent 50%)}.account-nav{position:relative;z-index:2;height:76px;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(20px,4vw,72px);border-bottom:1px solid rgba(255,255,255,.18);background:rgba(3,16,28,.38);backdrop-filter:blur(12px)}.account-brand{display:flex;align-items:center;gap:12px}.account-brand>span{display:grid;width:42px;height:42px;place-items:center;background:#1669ad;font-weight:900}.account-brand strong,.account-brand small{display:block}.account-brand small{margin-top:2px;color:#adc3d2;font-size:11px}.back-link{display:flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,.55);padding:10px 16px;font-size:13px;font-weight:900}.account-content{position:relative;z-index:1;min-height:calc(100vh - 76px);display:grid;grid-template-columns:minmax(0,1fr) minmax(440px,620px);align-items:center;gap:clamp(50px,8vw,150px);padding:70px clamp(24px,8vw,140px)}.account-intro{max-width:680px}.account-intro>p:first-child,.panel-head>p{color:#6bc8ef;font-size:12px;font-weight:900;letter-spacing:.18em}.account-intro h1{margin-top:22px;font-size:clamp(48px,6vw,88px);line-height:1.02;font-weight:900;letter-spacing:-.045em}.intro-line{width:64px;height:3px;margin-top:30px;background:#63c5ed}.intro-copy{max-width:600px;margin-top:24px;color:#d3e2ec;font-size:16px;line-height:1.9}.account-panel{padding:38px;background:rgba(255,255,255,.96);color:#173047;box-shadow:0 32px 90px rgba(0,0,0,.35)}.panel-head h2{margin-top:7px;font-size:30px;font-weight:900}.panel-head span{display:block;margin-top:9px;color:#6c8192;font-size:13px;line-height:1.7}.role-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;margin-top:28px;background:#dbe5ec;border:1px solid #dbe5ec}.role-grid article{display:flex;gap:12px;padding:18px;background:#fff}.role-grid article>span{color:#2075b6;font-size:11px;font-weight:900}.role-grid strong{font-size:15px}.role-grid p{margin-top:6px;color:#667d8f;font-size:12px;line-height:1.65}.scope-note{display:flex;gap:12px;margin-top:22px;padding:15px;background:#edf6fc;color:#176cac}.scope-note svg{flex:none}.scope-note strong,.scope-note span{display:block}.scope-note span{margin-top:4px;color:#60798c;font-size:11px;line-height:1.6}.account-action{display:flex;min-height:50px;align-items:center;justify-content:center;gap:10px;margin-top:22px;background:#176cac;color:#fff;font-weight:900}
@media(max-width:980px){.account-content{grid-template-columns:1fr;padding-top:100px}.account-intro{max-width:760px}.account-panel{max-width:760px;width:100%}}@media(max-width:600px){.account-nav{height:66px}.account-brand small{display:none}.account-content{padding:80px 18px 36px}.account-intro h1{font-size:46px}.account-panel{padding:24px}.role-grid{grid-template-columns:1fr}.panel-head h2{font-size:25px}}
.account-intro h1{max-width:720px;font-size:clamp(44px,5.2vw,76px);line-height:1.08;letter-spacing:-.035em;text-wrap:balance}.account-panel{border-top:3px solid #2b84c3}.panel-head h2{line-height:1.25;text-wrap:balance}.account-page{background-size:108% auto;background-repeat:no-repeat}@media(max-aspect-ratio:4/3){.account-page{background-size:auto 108%}}
</style>
