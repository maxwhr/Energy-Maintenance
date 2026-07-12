<template>
  <div class="public-portal">
    <header class="public-nav">
      <button class="public-brand" type="button" @click="scrollToHome">
        <span class="brand-mark">EM</span>
        <span><strong>Energy-Maintenance</strong><small>光伏逆变器检修工作台</small></span>
      </button>
      <nav class="public-links">
        <button type="button" @click="scrollToHome">首页</button>
        <button type="button" @click="scrollToCapabilities">能力</button>
        <button type="button" @click="scrollToScope">闭环</button>
        <button type="button" @click="scrollToAccount">账号说明</button>
      </nav>
      <RouterLink class="nav-login" to="/auth/login">进入系统</RouterLink>
    </header>

    <main>
      <section id="home" class="hero-section" :style="{ backgroundImage: `url(${solarField})` }">
        <div class="hero-shade"></div>
        <div class="hero-content reveal-up">
          <p class="eyebrow"><span></span> Huawei · Sungrow · PV Inverter</p>
          <h1>让每一次检修<br /><em>都有据可循</em></h1>
          <p class="hero-copy">面向华为 SUN2000、FusionSolar 与阳光电源 SG 系列，连接知识、诊断、任务与现场。</p>
          <div class="hero-actions">
            <RouterLink class="primary-cta" to="/auth/login">进入检修工作台 <ArrowDownRight :size="18" /></RouterLink>
            <button class="ghost-cta" type="button" @click="scrollToScope">了解核心能力</button>
          </div>
        </div>
        <div class="scroll-cue"><span></span>滚动探索</div>
      </section>

      <section id="scope" class="scope-section orbit-section">
        <div class="scope-heading scroll-reveal"><h2>从知识进入现场<br />再让经验回到知识</h2><p class="scope-lead">悬停任一环节可暂停闭环并查看说明，点击即可前往对应能力章节。</p></div>
        <div class="orbit-layout">
          <div class="orbit-wrap" :class="{ 'is-paused': discPaused }">
            <div class="orbit-guide orbit-guide-outer"></div><div class="orbit-guide orbit-guide-inner"></div>
            <div class="orbit-disc">
              <button
                v-for="(item, index) in flow"
                :key="item.title"
                class="orbit-item"
                :class="{ active: activeOrbit === index }"
                :style="{ '--angle': `${index * 90}deg`, '--counter-angle': `${index * -90}deg` }"
                type="button"
                @mouseenter="activeOrbit = index; discPaused = true"
                @mouseleave="discPaused = false"
                @focus="activeOrbit = index; discPaused = true"
                @blur="discPaused = false"
                @click="scrollToSection(item.target)"
              >
                <span class="orbit-item-inner"><small>0{{ index + 1 }}</small><strong>{{ item.title }}</strong></span>
              </button>
            </div>
            <div class="orbit-core"><span>EM</span><strong>检修闭环</strong><small>TRACEABLE</small></div>
          </div>
          <aside class="orbit-detail" aria-live="polite">
            <div class="detail-index">0{{ activeOrbit + 1 }}</div>
            <p>WORKFLOW NODE</p><h3>{{ flow[activeOrbit].title }}</h3><div class="detail-line"></div><p class="detail-copy">{{ flow[activeOrbit].text }}</p>
            <button type="button" @click="scrollToSection(flow[activeOrbit].target)">查看对应能力 <ArrowDownRight :size="17" /></button>
          </aside>
        </div>
      </section>

      <div id="capabilities" class="narrative-stack">
        <section class="narrative-stage stage-device">
          <div class="narrative-card">
            <div class="narrative-visual"><img :src="dualInverter" alt="华为与阳光电源光伏逆变器现场检修" /></div>
            <div class="narrative-copy scroll-reveal">
              <p class="section-number">01 / 设备与现场</p><h2>聚焦国产光伏<br />逆变器检修</h2>
              <p>围绕华为与阳光电源设备，沉淀手册、告警、规程、案例与检修记录，保持厂家、系列和设备全程可追溯。</p>
              <div class="story-tags"><span>SUN2000</span><span>FusionSolar</span><span>SG 系列</span></div>
            </div>
          </div>
        </section>
        <section class="narrative-stage stage-knowledge">
          <div class="narrative-card narrative-reverse">
            <div class="narrative-visual framed-visual"><img :src="knowledgeSearch" alt="检修知识检索与来源追溯" /></div>
            <div class="narrative-copy scroll-reveal">
              <p class="section-number">02 / 知识与来源</p><h2>检索真实资料<br />追溯每条来源</h2>
              <p>答案来自已经入库的知识切片。文档、章节、页码、引用内容和 trace_id 共同构成可核验的检修依据。</p>
              <ul class="feature-list"><li>真实文档切片召回</li><li>厂家与产品系列过滤</li><li>问答记录持续沉淀</li></ul>
            </div>
          </div>
        </section>
        <section class="narrative-stage stage-diagnosis">
          <div class="narrative-card diagnosis-card">
            <div class="diagnosis-art scroll-reveal"><div class="art-frame"><img :src="faultDiagnosis" alt="光伏逆变器故障辅助诊断" /></div></div>
            <div class="narrative-copy scroll-reveal">
              <p class="section-number">03 / 辅助诊断</p><h2>定位可能原因<br />守住安全边界</h2>
              <p>结合告警代码、现场现象与知识依据，输出可能原因、检查步骤、安全提示和建议措施，不替代现场工程师判断。</p>
              <div class="diagnosis-points"><span>原因定位</span><span>风险预警</span><span>检查步骤</span><span>处理建议</span></div>
            </div>
          </div>
        </section>
        <section class="narrative-stage stage-workflow">
          <div class="narrative-card workflow-card">
            <div class="narrative-copy scroll-reveal">
              <p class="section-number">04 / 任务闭环</p><h2>让每一次作业<br />形成完整记录</h2>
              <p>从诊断结果创建检修任务，经过分派、执行、完成与复盘，将现场处理过程重新沉淀为可查询、可核验的运维经验。</p>
              <div class="workflow-metrics"><div><strong>4</strong><span>规范任务状态</span></div><div><strong>1</strong><span>统一追溯链路</span></div><div><strong>全程</strong><span>操作记录留痕</span></div></div>
            </div>
            <div class="workflow-board scroll-reveal">
              <div class="workflow-line"></div>
              <article v-for="(item, index) in taskFlow" :key="item.title" class="workflow-node">
                <div class="node-marker"><span>0{{ index + 1 }}</span></div>
                <div class="node-copy"><small>{{ item.status }}</small><h3>{{ item.title }}</h3><p>{{ item.text }}</p></div>
              </article>
              <div class="workflow-trace"><span>TRACE ID</span><strong>诊断依据 · 任务过程 · 处理结果</strong></div>
            </div>
          </div>
        </section>
      </div>

      <section id="account-guide" class="login-section account-guide" :style="{ backgroundImage: `url(${solarField})` }">
        <div class="login-shade"></div>
        <div class="login-intro"><p class="section-number">ACCOUNT &amp; PERMISSION</p><h2>以清晰权限<br />守护专业作业</h2><p>系统账号由管理员统一创建并分配角色，让知识审核、诊断操作、任务流转与审计记录始终处于可信边界内。</p></div>
        <div class="account-guide-card">
          <div class="guide-head"><p>账号说明</p><h2>按实际职责分配访问权限</h2><span>当前版本不开放自助注册，请联系系统管理员创建账号。</span></div>
          <div class="guide-roles"><article v-for="item in roleCards" :key="item.role"><strong>{{ item.role }}</strong><p>{{ item.desc }}</p></article></div>
          <RouterLink class="guide-action" to="/auth/login">使用已分配账号进入系统 <ArrowDownRight :size="17" /></RouterLink>
        </div>
      </section>
    </main>
    <footer class="public-footer"><div class="public-brand"><span class="brand-mark">EM</span><span><strong>Energy-Maintenance</strong><small>华为 / 阳光电源光伏逆变器检修</small></span></div><p>知识可追溯 · 诊断有边界 · 作业成闭环</p></footer>
    <AppToast />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { ArrowDownRight } from '@lucide/vue'
import AppToast from '@/components/AppToast.vue'
import solarField from '@/assets/auth/solar-field.png'
import dualInverter from '@/assets/auth/dual-inverter.png'
import knowledgeSearch from '@/assets/auth/knowledge-search.png'
import faultDiagnosis from '@/assets/auth/fault-diagnosis.png'

const activeOrbit = ref(0)
const discPaused = ref(false)
const flow = [
  { title: '资料入库', text: '上传设备手册、告警代码与检修规程，让现场资料形成结构清晰、可持续维护的知识基础。', target: '.stage-device' },
  { title: '知识检索', text: '从真实知识切片召回答案与引用，让每一条检修建议都能够回到文档、章节与页码。', target: '.stage-knowledge' },
  { title: '辅助诊断', text: '结合告警与现场现象形成可能原因、检查步骤、安全提示和处理建议。', target: '.stage-diagnosis' },
  { title: '任务闭环', text: '把诊断结果转化为检修任务，并将执行过程与最终结果沉淀为可追溯记录。', target: '.stage-workflow' }
]
const taskFlow = [
  { status: 'PENDING', title: '创建与分派', text: '关联设备、故障类型、诊断记录与责任人。' },
  { status: 'IN PROGRESS', title: '执行与记录', text: '按检查步骤开展作业，持续记录现场处理过程。' },
  { status: 'COMPLETED', title: '完成与确认', text: '填写处理结果，保留时间、人员和操作轨迹。' },
  { status: 'TRACEABLE', title: '复盘与沉淀', text: '任务结果进入记录中心，支撑后续查询与知识贡献。' }
]
const roleCards = [
  { role: '管理员', desc: '维护账号、系统状态和权限策略。' },
  { role: '专家', desc: '审核知识资料并参与经验沉淀。' },
  { role: '工程师', desc: '执行问答、诊断与检修任务。' },
  { role: '只读用户', desc: '查看已授权的运行与追溯信息。' }
]
let revealObserver: IntersectionObserver | null = null

onMounted(() => {
  revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => entry.target.classList.toggle('is-visible', entry.isIntersecting))
  }, { threshold: 0.32 })
  document.querySelectorAll('.scroll-reveal').forEach((element) => revealObserver?.observe(element))
  if (window.location.hash === '#account-guide') {
    window.requestAnimationFrame(() => scrollToAccount())
  }
})

onBeforeUnmount(() => revealObserver?.disconnect())

const scroll = (selector: string) => document.querySelector(selector)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
const scrollToSection = (selector: string) => scroll(selector)
const scrollToHome = () => scroll('#home'); const scrollToCapabilities = () => scroll('#capabilities'); const scrollToScope = () => scroll('#scope')
const scrollToAccount = () => scroll('#account-guide')
</script>

<style scoped>
.public-portal{--navy:#081d31;--blue:#1669ad;--cyan:#57b7e9;min-height:100vh;background:#061727;color:#fff}.public-nav{position:fixed;inset:0 0 auto;z-index:50;height:76px;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(20px,4vw,72px);border-bottom:1px solid rgba(255,255,255,.16);background:rgba(5,20,34,.6);backdrop-filter:blur(14px)}.public-brand{display:flex;align-items:center;gap:12px;text-align:left}.public-brand strong,.public-brand small{display:block}.public-brand strong{font-size:15px}.public-brand small{margin-top:2px;font-size:11px;color:#a8bfd1}.brand-mark{display:grid;width:42px;height:42px;place-items:center;border:1px solid rgba(255,255,255,.32);background:#1669ad;font-weight:900}.public-links{display:flex;gap:32px;font-size:13px;font-weight:700}.public-links button,.public-links a{position:relative;color:#d8e8f4}.public-links button:after,.public-links a:after{content:"";position:absolute;left:0;right:100%;bottom:-9px;height:2px;background:#63c3ef;transition:right .25s}.public-links button:hover:after,.public-links a:hover:after{right:0}.nav-login{border:1px solid rgba(255,255,255,.65);padding:10px 18px;font-weight:800}.hero-section,.story-section,.login-section{position:relative;min-height:100vh;background-size:cover;background-position:center}.hero-section{display:flex;align-items:center;padding:110px clamp(24px,7vw,120px) 70px}.hero-shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,16,28,.88) 0%,rgba(3,16,28,.55) 46%,rgba(3,16,28,.12) 78%),linear-gradient(0deg,rgba(3,16,28,.45),transparent 45%)}.hero-content{position:relative;z-index:1;max-width:830px}.eyebrow,.section-number{font-size:12px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.eyebrow{display:flex;align-items:center;gap:12px;color:#bfe9fb}.eyebrow span{width:42px;height:2px;background:#57b7e9}.hero-content h1{margin-top:24px;font-size:clamp(48px,7vw,108px);line-height:.98;letter-spacing:-.045em;font-weight:900}.hero-content h1 em{color:#69c8ef;font-style:normal}.hero-copy{max-width:650px;margin-top:30px;font-size:clamp(16px,1.5vw,21px);line-height:1.85;color:#d4e5f1}.hero-actions{display:flex;gap:14px;margin-top:40px}.primary-cta,.ghost-cta{min-height:52px;padding:0 24px;font-weight:900}.primary-cta{display:flex;align-items:center;gap:10px;background:#fff;color:#0a2841}.ghost-cta{border:1px solid rgba(255,255,255,.6)}.scroll-cue{position:absolute;z-index:1;left:50%;bottom:24px;display:flex;flex-direction:column;align-items:center;gap:8px;transform:translateX(-50%);font-size:10px;letter-spacing:.2em;color:#d9eaf5}.scroll-cue span{width:1px;height:42px;background:linear-gradient(#fff,transparent);animation:scrollPulse 1.6s infinite}.story-section{display:flex;align-items:center;justify-content:flex-end;padding:100px clamp(24px,8vw,140px)}.story-overlay{position:absolute;inset:0;background:linear-gradient(90deg,rgba(3,17,30,.15),rgba(3,17,30,.82) 68%,rgba(3,17,30,.94))}.story-copy{position:relative;z-index:1;width:min(560px,100%)}.section-number{color:#64c5ee}.story-copy h2,.split-copy h2,.scope-heading h2,.login-intro h2{margin-top:18px;font-size:clamp(38px,4.5vw,70px);line-height:1.08;font-weight:900;letter-spacing:-.035em}.story-copy>p:last-of-type,.split-copy>p:last-of-type,.login-intro>p:last-of-type{margin-top:24px;font-size:16px;line-height:1.9;color:#c7d9e7}.story-tags{display:flex;flex-wrap:wrap;gap:10px;margin-top:30px}.story-tags span{border:1px solid rgba(255,255,255,.28);padding:9px 14px;font-size:12px}.split-story{display:grid;grid-template-columns:1fr 1fr}.split-panel{position:relative;min-height:78vh;background-size:cover;background-position:center;display:flex;align-items:flex-end;padding:clamp(24px,5vw,72px)}.split-overlay{position:absolute;inset:0;background:linear-gradient(0deg,rgba(4,19,33,.94),rgba(4,19,33,.12) 75%)}.split-copy{position:relative;z-index:1;max-width:560px}.split-copy h2{font-size:clamp(34px,3.4vw,56px)}.scope-section{padding:110px clamp(24px,7vw,120px);background:#f4f8fb;color:#10283c}.scope-heading{max-width:760px}.scope-steps{display:grid;grid-template-columns:repeat(4,1fr);margin-top:64px;border-top:1px solid #b9cedd}.scope-step{padding:28px 28px 10px 0;border-right:1px solid #cfdee8}.scope-step+ .scope-step{padding-left:28px}.scope-step span{font-size:12px;font-weight:900;color:#2174b4}.scope-step strong{display:block;margin-top:34px;font-size:21px}.scope-step p{margin-top:12px;font-size:14px;line-height:1.7;color:#60788b}.login-section{display:grid;grid-template-columns:1fr minmax(360px,520px);align-items:center;gap:clamp(40px,8vw,140px);padding:110px clamp(24px,8vw,140px);background-position:center}.login-shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(4,19,33,.94),rgba(4,19,33,.55)),rgba(4,19,33,.25)}.login-intro,.login-card{position:relative;z-index:1}.login-intro{max-width:680px}.login-card{display:grid;gap:20px;padding:38px;background:rgba(255,255,255,.96);color:#173047;box-shadow:0 32px 90px rgba(0,0,0,.3)}.login-card h2{margin-top:5px;font-size:31px;font-weight:900}.login-card>div>p:last-child{margin-top:5px;color:#72889a}.login-kicker{color:#176cac;font-size:12px;font-weight:900;letter-spacing:.16em}.login-card label span{display:block;margin-bottom:8px;font-size:13px;font-weight:800}.public-input{width:100%;border:1px solid #c7d5df;background:#fff;padding:13px 14px;outline:none;transition:.2s}.public-input:focus{border-color:#176cac;box-shadow:0 0 0 3px rgba(23,108,172,.12)}.login-error{border-left:3px solid #cf3f42;background:#fff0f0;padding:10px 12px;color:#a7262a}.login-submit{display:flex;min-height:50px;align-items:center;justify-content:center;gap:9px;background:#176cac;color:#fff;font-weight:900}.login-submit:disabled{opacity:.55}.login-footer{display:flex;justify-content:space-between;gap:15px;font-size:11px;color:#72889a}.login-footer a{color:#176cac;font-weight:900;white-space:nowrap}.public-footer{display:flex;align-items:center;justify-content:space-between;padding:34px clamp(24px,7vw,120px);background:#03111d;border-top:1px solid rgba(255,255,255,.1)}.public-footer p{font-size:12px;color:#7992a5;letter-spacing:.12em}.reveal-up{animation:revealUp .9s both}@keyframes revealUp{from{opacity:0;transform:translateY(32px)}to{opacity:1;transform:none}}@keyframes scrollPulse{0%,100%{opacity:.25;transform:scaleY(.6);transform-origin:top}50%{opacity:1;transform:scaleY(1)}}
.narrative-stack{position:relative;background:#eaf1f5}.narrative-stage{position:relative;height:145vh}.narrative-card{position:sticky;top:0;min-height:100vh;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(360px,.75fr);align-items:center;gap:clamp(36px,6vw,110px);padding:110px clamp(24px,7vw,120px);overflow:hidden;box-shadow:0 -26px 70px rgba(3,18,30,.18)}.stage-device{z-index:1}.stage-device .narrative-card{background:#071b2c}.stage-knowledge{z-index:2}.stage-knowledge .narrative-card{background:#f4f7f9;color:#122b40}.stage-diagnosis{z-index:3;height:115vh}.stage-diagnosis .narrative-card{background:#0b3150}.narrative-visual{height:min(68vh,720px);overflow:hidden}.narrative-visual img{width:100%;height:100%;object-fit:cover;transition:transform 1.1s cubic-bezier(.2,.7,.2,1)}.narrative-card:hover .narrative-visual img{transform:scale(1.025)}.framed-visual{height:min(62vh,650px);padding:18px;background:#fff;box-shadow:0 25px 70px rgba(18,43,64,.16)}.narrative-reverse{grid-template-columns:minmax(360px,.72fr) minmax(0,1.28fr)}.narrative-reverse .narrative-visual{order:2}.narrative-reverse .narrative-copy{order:1}.narrative-copy{max-width:590px}.narrative-copy h2{margin-top:18px;font-size:clamp(38px,4.7vw,72px);line-height:1.05;font-weight:900;letter-spacing:-.04em}.narrative-copy>p:not(.section-number){margin-top:25px;font-size:16px;line-height:1.9;color:#bcd0df}.stage-knowledge .narrative-copy>p:not(.section-number){color:#627a8c}.scroll-reveal{opacity:0;transform:translateY(50px);transition:opacity .8s ease,transform .9s cubic-bezier(.2,.7,.2,1)}.scroll-reveal.is-visible{opacity:1;transform:none}.feature-list{display:grid;gap:0;margin-top:32px;border-top:1px solid #c8d7e1}.feature-list li{padding:14px 0;border-bottom:1px solid #d5e0e7;font-size:13px;font-weight:800}.diagnosis-card{grid-template-columns:minmax(0,1fr) minmax(360px,.8fr)}.diagnosis-art{position:relative;max-width:850px}.art-frame{position:relative;padding:16px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22)}.art-frame img{display:block;width:100%;height:auto}.art-index{position:absolute;right:-20px;bottom:-50px;color:rgba(255,255,255,.08);font-size:clamp(120px,16vw,260px);line-height:1;font-weight:900}.diagnosis-points{display:grid;grid-template-columns:1fr 1fr;gap:1px;margin-top:32px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.18)}.diagnosis-points span{padding:15px;background:#0b3150;font-size:12px;font-weight:900}.scope-section{position:relative;z-index:5}
@media(max-width:900px){.public-links{display:none}.scope-steps{grid-template-columns:1fr 1fr}.login-section{grid-template-columns:1fr}.login-intro{padding-top:60px}.public-footer{align-items:flex-start;gap:24px;flex-direction:column}.narrative-card,.narrative-reverse,.diagnosis-card{grid-template-columns:1fr;padding-top:96px;padding-bottom:48px}.narrative-stage{height:150vh}.narrative-reverse .narrative-visual,.narrative-reverse .narrative-copy{order:initial}.narrative-visual{height:48vh}.narrative-copy h2{font-size:44px}}@media(max-width:600px){.public-nav{height:66px}.public-brand small{display:none}.nav-login{padding:9px 12px}.hero-section{padding-top:100px}.hero-content h1{font-size:48px}.hero-actions{align-items:stretch;flex-direction:column}.scope-steps{grid-template-columns:1fr}.scope-step,.scope-step+.scope-step{padding:24px 0;border-right:0;border-bottom:1px solid #cfdee8}.login-card{padding:24px}.login-footer{flex-direction:column}.public-footer p{line-height:1.8}.narrative-stage{height:auto}.narrative-card{position:relative;min-height:100vh;gap:32px;padding:88px 18px 46px}.narrative-visual{height:38vh}.framed-visual{padding:8px}.narrative-copy h2{font-size:38px}.diagnosis-points{grid-template-columns:1fr 1fr}}
.hero-content h1,.narrative-copy h2,.scope-heading h2,.login-intro h2{text-wrap:balance}.narrative-card:before{content:"";position:absolute;inset:0 0 auto;height:1px;background:linear-gradient(90deg,transparent,rgba(111,197,235,.72),transparent)}.framed-visual img{object-position:center}.stage-knowledge .section-number{color:#176cac}.login-card{border-top:3px solid #5abce7}.art-index{display:none!important}
.orbit-section{overflow:hidden;background:radial-gradient(circle at 30% 50%,rgba(33,116,180,.08),transparent 34%),#f4f8fb}.scope-lead{max-width:620px;margin-top:22px;color:#60788b;font-size:15px;line-height:1.8}.orbit-layout{display:grid;grid-template-columns:minmax(500px,1fr) minmax(300px,.62fr);align-items:center;gap:clamp(50px,8vw,140px);margin-top:48px}.orbit-wrap{position:relative;width:min(68vw,620px);aspect-ratio:1;margin-inline:auto}.orbit-guide{position:absolute;inset:8%;border:1px solid rgba(23,108,172,.18);border-radius:50%}.orbit-guide-outer:before,.orbit-guide-outer:after{content:"";position:absolute;inset:-9px;border-top:2px solid #2680bd;border-radius:50%;transform:rotate(42deg)}.orbit-guide-outer:after{border-top-color:transparent;border-bottom:2px solid rgba(23,108,172,.38);transform:rotate(-28deg)}.orbit-guide-inner{inset:27%;border-style:dashed}.orbit-disc{position:absolute;inset:0;animation:orbitSpin 34s linear infinite}.orbit-wrap.is-paused .orbit-disc,.orbit-wrap.is-paused .orbit-item-inner{animation-play-state:paused}.orbit-item{--radius:clamp(170px,19vw,250px);position:absolute;top:50%;left:50%;width:130px;height:130px;margin:-65px;border:1px solid rgba(23,108,172,.2);border-radius:50%;background:rgba(255,255,255,.92);box-shadow:0 14px 40px rgba(23,68,100,.11);color:#17354b;transform:rotate(var(--angle)) translateY(calc(var(--radius) * -1)) rotate(calc(var(--angle) * -1));transition:border-color .25s,box-shadow .25s,background .25s,color .25s;cursor:pointer}.orbit-item:before{content:"";position:absolute;inset:8px;border:1px solid rgba(23,108,172,.13);border-radius:50%;transition:.25s}.orbit-item:hover,.orbit-item:focus-visible,.orbit-item.active{border-color:#2a8bc8;background:#176cac;color:#fff;box-shadow:0 18px 54px rgba(23,108,172,.3);outline:none}.orbit-item:hover:before,.orbit-item:focus-visible:before,.orbit-item.active:before{border-color:rgba(255,255,255,.38)}.orbit-item-inner{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;animation:orbitCounterSpin 34s linear infinite}.orbit-item small{font-size:10px;font-weight:900;letter-spacing:.16em;opacity:.7}.orbit-item strong{margin-top:6px;font-size:16px}.orbit-core{position:absolute;inset:33%;display:flex;flex-direction:column;align-items:center;justify-content:center;border-radius:50%;background:#071f34;color:#fff;box-shadow:0 25px 70px rgba(7,31,52,.28),inset 0 0 0 12px rgba(255,255,255,.035)}.orbit-core span{font-size:26px;font-weight:900;color:#65c3eb}.orbit-core strong{margin-top:7px;font-size:18px}.orbit-core small{margin-top:5px;color:#89a6ba;font-size:8px;letter-spacing:.2em}.orbit-detail{position:relative;max-width:460px;padding:36px 0 36px 42px;border-left:1px solid #bfd2df}.detail-index{position:absolute;top:-40px;right:0;color:rgba(23,108,172,.08);font-size:130px;line-height:1;font-weight:900}.orbit-detail>p:first-of-type{position:relative;color:#2174b4;font-size:10px;font-weight:900;letter-spacing:.18em}.orbit-detail h3{position:relative;margin-top:12px;font-size:clamp(34px,4vw,58px);font-weight:900;letter-spacing:-.035em}.detail-line{width:54px;height:3px;margin-top:22px;background:#2384c2}.detail-copy{min-height:86px;margin-top:22px;color:#60788b;font-size:15px;line-height:1.85}.orbit-detail button{display:flex;align-items:center;gap:9px;margin-top:28px;color:#176cac;font-size:13px;font-weight:900}.orbit-detail button:hover{color:#0c466f}@keyframes orbitSpin{to{transform:rotate(360deg)}}@keyframes orbitCounterSpin{to{transform:rotate(-360deg)}}
@media(max-width:1000px){.orbit-layout{grid-template-columns:1fr}.orbit-detail{max-width:620px;margin-inline:auto}.orbit-wrap{width:min(82vw,580px)}.orbit-item{--radius:clamp(155px,29vw,230px)}}@media(max-width:600px){.orbit-section{padding-inline:18px}.orbit-wrap{width:92vw;max-width:410px}.orbit-item{--radius:clamp(125px,36vw,165px);width:104px;height:104px;margin:-52px}.orbit-item strong{font-size:13px}.orbit-core{inset:34%}.orbit-core span{font-size:20px}.orbit-core strong{font-size:14px}.orbit-detail{padding-left:22px}.detail-index{font-size:90px}}
.orbit-item{transform:rotate(var(--angle)) translateY(calc(var(--radius) * -1)) rotate(var(--counter-angle))!important}.hero-section,.login-section{background-size:108% auto;background-repeat:no-repeat}.narrative-visual img{transform:scale(1.08);transform-origin:center}.narrative-card:hover .narrative-visual img{transform:scale(1.105)}.art-frame{position:relative;aspect-ratio:2848/1600;overflow:hidden}.art-frame img{position:absolute;inset:0;width:116%;height:116%;max-width:none;object-fit:cover;transform:translate(-4%,-4%);transform-origin:center}.framed-visual img{width:116%;height:116%;max-width:none;object-fit:cover;transform:translate(-4%,-4%)}.narrative-card:hover .framed-visual img{transform:translate(-4%,-4%)}
@media(max-aspect-ratio:4/3){.hero-section,.login-section{background-size:auto 108%}}
.hero-content h1{line-height:1.06}.account-guide-card{position:relative;z-index:1;padding:38px;background:rgba(255,255,255,.97);border-top:3px solid #5dc2eb;color:#173047;box-shadow:0 32px 90px rgba(0,0,0,.32)}.guide-head>p{color:#176cac;font-size:11px;font-weight:900;letter-spacing:.16em}.guide-head h2{margin-top:8px;font-size:28px;line-height:1.25;font-weight:900}.guide-head>span{display:block;margin-top:8px;color:#718798;font-size:13px;line-height:1.7}.guide-roles{display:grid;grid-template-columns:1fr 1fr;gap:1px;margin-top:25px;background:#d7e3eb;border:1px solid #d7e3eb}.guide-roles article{padding:17px;background:#fff}.guide-roles strong{font-size:14px}.guide-roles p{margin-top:6px;color:#667e90;font-size:11px;line-height:1.6}.guide-action{display:flex;min-height:50px;align-items:center;justify-content:center;gap:9px;margin-top:22px;background:#176cac;color:#fff;font-weight:900}.guide-action:hover{background:#0f5689}@media(max-width:600px){.account-guide-card{padding:24px}.guide-roles{grid-template-columns:1fr}}
.stage-workflow{z-index:4;height:130vh}.stage-workflow .narrative-card{background:#eef4f7;color:#122b40}.workflow-card{grid-template-columns:minmax(360px,.72fr) minmax(0,1.28fr)}.stage-workflow .narrative-copy>p:not(.section-number){color:#60798c}.workflow-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;margin-top:34px;background:#cbdbe5;border:1px solid #cbdbe5}.workflow-metrics>div{padding:18px 14px;background:#f8fbfc}.workflow-metrics strong,.workflow-metrics span{display:block}.workflow-metrics strong{color:#176cac;font-size:25px}.workflow-metrics span{margin-top:4px;color:#637b8d;font-size:10px}.workflow-board{position:relative;display:grid;gap:0;padding:30px 36px;background:#fff;border:1px solid #d2e0e8;box-shadow:0 28px 70px rgba(18,43,64,.13)}.workflow-line{position:absolute;top:64px;bottom:96px;left:61px;width:1px;background:linear-gradient(#2585c3,#a6c9de)}.workflow-node{position:relative;display:grid;grid-template-columns:52px 1fr;gap:20px;padding:18px 0;border-bottom:1px solid #e0e9ee}.node-marker{position:relative;z-index:1;display:grid;width:52px;height:52px;place-items:center;border:1px solid #9ec7df;border-radius:50%;background:#fff;color:#176cac;font-size:10px;font-weight:900}.node-copy small{color:#2784bd;font-size:9px;font-weight:900;letter-spacing:.16em}.node-copy h3{margin-top:5px;font-size:18px;font-weight:900}.node-copy p{margin-top:5px;color:#687f90;font-size:12px;line-height:1.65}.workflow-trace{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-top:24px;padding:15px 18px;background:#0a2b45;color:#fff}.workflow-trace span{color:#65c3eb;font-size:9px;font-weight:900;letter-spacing:.16em}.workflow-trace strong{font-size:11px}@media(max-width:900px){.workflow-card{grid-template-columns:1fr}.stage-workflow{height:150vh}.workflow-board{padding:22px}.workflow-line{left:47px}}@media(max-width:600px){.stage-workflow{height:auto}.workflow-metrics{grid-template-columns:1fr}.workflow-board{padding:16px}.workflow-node{grid-template-columns:44px 1fr;gap:13px}.node-marker{width:44px;height:44px}.workflow-line{left:37px}.workflow-trace{align-items:flex-start;flex-direction:column}}
#scope,.narrative-stage,#account-guide{scroll-margin-top:76px}@media(prefers-reduced-motion:reduce){.orbit-disc,.orbit-item-inner{animation:none!important}.scroll-reveal{opacity:1;transform:none;transition:none}}
</style>
