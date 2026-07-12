<template>
  <main class="denied-page" :style="{ backgroundImage: `url(${accessDenied})` }">
    <div class="denied-overlay"></div>
    <RouterLink class="denied-brand" to="/login"><span>EM</span><div><strong>Energy-Maintenance</strong><small>光伏逆变器检修工作台</small></div></RouterLink>
    <section class="denied-card">
      <p>ACCESS CONTROL / 403</p>
      <div class="denied-code">403</div>
      <h1>当前角色无权<br />访问此页面</h1>
      <p class="denied-copy">系统已阻止本次访问。请返回运行总览，或联系管理员核对账号角色与功能授权。</p>
      <div class="denied-actions"><RouterLink class="primary" to="/dashboard">返回运行总览 <ArrowRight :size="17" /></RouterLink><RouterLink class="secondary" to="/login">重新登录</RouterLink></div>
    </section>
    <div class="denied-note"><ShieldAlert :size="18" /><span>权限由后端统一校验 · 操作边界全程保留</span></div>
  </main>
</template>

<script setup lang="ts">
import { ArrowRight, ShieldAlert } from '@lucide/vue'
import accessDenied from '@/assets/auth/access-denied.png'
</script>

<style scoped>
.denied-page{position:relative;min-height:100vh;background-size:cover;background-position:center;display:flex;align-items:center;padding:110px clamp(24px,9vw,160px);color:#fff}.denied-overlay{position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,15,27,.96),rgba(3,15,27,.73) 48%,rgba(3,15,27,.2)),linear-gradient(0deg,rgba(3,15,27,.6),transparent)}.denied-brand{position:absolute;z-index:2;top:24px;left:clamp(24px,4vw,72px);display:flex;align-items:center;gap:12px}.denied-brand>span{display:grid;width:42px;height:42px;place-items:center;background:#1669ad;font-weight:900}.denied-brand strong,.denied-brand small{display:block}.denied-brand small{margin-top:2px;color:#abc1d1;font-size:11px}.denied-card{position:relative;z-index:1;max-width:700px;animation:deniedReveal .8s both}.denied-card>p:first-child{color:#68c8ef;font-size:12px;font-weight:900;letter-spacing:.18em}.denied-code{margin-top:22px;color:rgba(255,255,255,.13);font-size:clamp(90px,14vw,200px);line-height:.78;font-weight:900;letter-spacing:-.08em}.denied-card h1{margin-top:-8px;font-size:clamp(44px,5.5vw,80px);line-height:1.03;font-weight:900;letter-spacing:-.045em}.denied-copy{max-width:590px;margin-top:26px;color:#cfdee9;font-size:16px;line-height:1.85}.denied-actions{display:flex;gap:12px;margin-top:36px}.denied-actions a{min-height:50px;padding:0 22px;display:flex;align-items:center;justify-content:center;gap:9px;font-weight:900}.denied-actions .primary{background:#fff;color:#102a40}.denied-actions .secondary{border:1px solid rgba(255,255,255,.55)}.denied-note{position:absolute;z-index:1;right:clamp(24px,4vw,72px);bottom:26px;display:flex;align-items:center;gap:9px;color:#b9ccda;font-size:11px;letter-spacing:.08em}@keyframes deniedReveal{from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:none}}@media(max-width:600px){.denied-page{padding:100px 20px 80px}.denied-brand small{display:none}.denied-actions{align-items:stretch;flex-direction:column}.denied-note{left:20px;right:20px;line-height:1.5}.denied-code{font-size:110px}}
.denied-page{background-size:108% auto;background-repeat:no-repeat}@media(max-aspect-ratio:4/3){.denied-page{background-size:auto 108%}}
</style>
