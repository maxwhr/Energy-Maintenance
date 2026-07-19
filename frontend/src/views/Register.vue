<template>
  <div class="account-page" :style="{ backgroundImage: `url(${fieldEngineer})` }">
    <div class="account-overlay"></div>
    <header class="account-nav">
      <RouterLink class="account-brand" to="/login">
        <span>EM</span>
        <div><strong>Energy-Maintenance</strong><small>华为 SUN2000 检修工作台</small></div>
      </RouterLink>
      <RouterLink class="back-link" to="/login"><ArrowLeft :size="16" /> 返回介绍页</RouterLink>
    </header>

    <main class="account-content">
      <section class="account-intro">
        <p>ACCOUNT &amp; PERMISSION</p>
        <h1>以清晰权限<br />守护专业作业</h1>
        <div class="intro-line"></div>
        <p class="intro-copy">账号创建、角色分配和关键业务操作均以服务端校验为准，确保知识审核、现场诊断、任务流转与审计记录处于可信边界。</p>
        <span class="scope-label">正式知识范围：Huawei SUN2000</span>
      </section>

      <section class="account-panel">
        <div class="panel-head">
          <p>账号申请说明</p>
          <h2>当前版本不开放自助注册</h2>
          <span>请联系系统管理员创建账号，并按照实际职责分配角色。</span>
        </div>
        <div class="role-grid">
          <article v-for="(item, index) in roleCards" :key="item.role">
            <span>0{{ index + 1 }}</span>
            <div><strong>{{ item.role }}</strong><p>{{ item.description }}</p></div>
          </article>
        </div>
        <div class="scope-note">
          <ShieldCheck :size="20" />
          <p><strong>权限与审计</strong><span>前端不会绕过后端权限。高风险操作仍需符合系统审批、确认和审计规则。</span></p>
        </div>
        <RouterLink class="account-action" to="/auth/login">使用已分配账号登录 <ArrowRight :size="17" /></RouterLink>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ArrowLeft, ArrowRight, ShieldCheck } from '@lucide/vue'
import fieldEngineer from '@/assets/auth/field-engineer.png'

const roleCards = [
  { role: '管理员', description: '维护账号、系统状态、服务配置和权限策略。' },
  { role: '专家', description: '审核知识资料、诊断依据与模型回答修正。' },
  { role: '工程师', description: '执行知识检索、故障诊断、SOP 和检修任务。' },
  { role: '只读用户', description: '查看授权范围内的运行总览与追溯信息。' }
]
</script>

<style scoped>
.account-page { position: relative; min-height: 100svh; overflow: hidden; background-position: center; background-size: cover; color: #fff; }
.account-overlay { position: absolute; inset: 0; background: rgb(3 16 28 / 72%); }
.account-nav { position: relative; z-index: 2; display: flex; height: 72px; align-items: center; justify-content: space-between; padding: 0 4vw; border-bottom: 1px solid rgb(255 255 255 / 18%); background: rgb(3 16 28 / 52%); backdrop-filter: blur(12px); }
.account-brand { display: flex; align-items: center; gap: 12px; }
.account-brand > span { display: grid; width: 42px; height: 42px; place-items: center; background: #176cac; color: #fff; font-weight: 900; }
.account-brand strong,
.account-brand small { display: block; letter-spacing: 0; }
.account-brand small { margin-top: 2px; color: #b5cad8; font-size: 11px; }
.back-link { display: flex; min-height: 40px; align-items: center; gap: 8px; border: 1px solid rgb(255 255 255 / 58%); padding: 0 15px; font-size: 13px; font-weight: 900; }
.back-link:hover,
.back-link:focus-visible { border-color: #69c8ee; background: #fff; color: #0b314c; outline: none; }
.account-content { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1fr) minmax(440px, 610px); min-height: calc(100svh - 72px); align-items: center; gap: 8vw; padding: 58px 8vw; }
.account-intro { max-width: 660px; }
.account-intro > p:first-child,
.panel-head > p { margin: 0; color: #69c8ee; font-size: 12px; font-weight: 900; }
.account-intro h1 { margin: 20px 0 0; font-size: 58px; line-height: 1.08; letter-spacing: 0; text-wrap: balance; }
.intro-line { width: 64px; height: 3px; margin-top: 28px; background: #69c8ee; }
.intro-copy { max-width: 590px; margin: 23px 0 0; color: #d4e3ec; font-size: 15px; line-height: 1.9; }
.scope-label { display: inline-flex; margin-top: 24px; border: 1px solid rgb(255 255 255 / 42%); background: rgb(3 16 28 / 40%); padding: 9px 13px; color: #fff; font-size: 11px; font-weight: 900; }
.account-panel { border-top: 3px solid #69c8ee; background: rgb(255 255 255 / 97%); padding: 36px; color: #173047; box-shadow: 0 30px 80px rgb(0 0 0 / 35%); }
.panel-head > p { color: #176cac; }
.panel-head h2 { margin: 7px 0 0; font-size: 29px; line-height: 1.25; }
.panel-head span { display: block; margin-top: 8px; color: #6c8192; font-size: 12px; line-height: 1.7; }
.role-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin-top: 26px; border: 1px solid #dbe5ec; background: #dbe5ec; }
.role-grid article { display: flex; min-height: 112px; gap: 12px; background: #fff; padding: 16px; }
.role-grid article > span { color: #2075b6; font-size: 10px; font-weight: 900; }
.role-grid strong { font-size: 14px; }
.role-grid p { margin: 6px 0 0; color: #667d8f; font-size: 11px; line-height: 1.65; }
.scope-note { display: flex; gap: 12px; margin-top: 20px; background: #edf6fc; padding: 14px; color: #176cac; }
.scope-note svg { flex: none; }
.scope-note p { margin: 0; }
.scope-note strong,
.scope-note span { display: block; }
.scope-note span { margin-top: 4px; color: #60798c; font-size: 11px; line-height: 1.6; }
.account-action { display: flex; min-height: 50px; align-items: center; justify-content: center; gap: 10px; margin-top: 20px; background: #176cac; color: #fff; font-weight: 900; }
.account-action:hover,
.account-action:focus-visible { background: #0d5488; outline: 3px solid rgb(23 108 172 / 24%); outline-offset: 3px; }

@media (max-width: 980px) {
  .account-content { grid-template-columns: 1fr; align-content: center; gap: 44px; padding-top: 82px; }
  .account-panel { width: min(700px, 100%); }
}

@media (max-width: 600px) {
  .account-nav { height: 66px; padding-inline: 18px; }
  .account-brand small { display: none; }
  .back-link { padding-inline: 11px; }
  .account-content { min-height: calc(100svh - 66px); padding: 66px 18px 32px; }
  .account-intro h1 { font-size: 40px; }
  .account-panel { padding: 24px; }
  .role-grid { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .account-page * { scroll-behavior: auto; transition: none; }
}
</style>
