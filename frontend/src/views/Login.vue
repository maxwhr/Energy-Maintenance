<template>
  <div class="public-home">
    <header class="public-nav" :class="{ 'menu-open': mobileMenuOpen }">
      <button class="public-brand" type="button" aria-label="返回首页顶部" @click="scrollTo('#home')">
        <span class="brand-mark">EM</span>
        <span class="brand-copy">
          <strong>Energy-Maintenance</strong>
          <small>华为 SUN2000 检修工作台</small>
        </span>
      </button>

      <button
        class="menu-toggle"
        type="button"
        :aria-expanded="mobileMenuOpen"
        aria-controls="public-navigation"
        aria-label="打开或关闭导航"
        @click="mobileMenuOpen = !mobileMenuOpen"
      >
        <X v-if="mobileMenuOpen" :size="21" />
        <Menu v-else :size="21" />
      </button>

      <nav id="public-navigation" class="public-links" aria-label="公开首页导航">
        <button type="button" @click="scrollTo('#home')">首页</button>
        <button type="button" @click="scrollTo('#capabilities')">核心能力</button>
        <button type="button" @click="scrollTo('#workflow')">检修闭环</button>
        <button type="button" @click="scrollTo('#support-scope')">支持范围</button>
        <button type="button" @click="scrollTo('#account-guide')">账号说明</button>
      </nav>

      <RouterLink class="nav-login" to="/auth/login">进入系统 <ArrowDownRight :size="17" /></RouterLink>
    </header>

    <main>
      <section id="home" class="hero-section" :style="{ backgroundImage: `url(${solarField})` }">
        <div class="hero-shade"></div>
        <div class="hero-content reveal-on-load">
          <p class="eyebrow"><span></span> 从知识进入现场 · HUAWEI SUN2000</p>
          <h1>让每一次检修<br />都有据可循</h1>
          <p class="hero-statement">华为 SUN2000 光伏逆变器检修知识工作台</p>
          <p class="hero-copy">
            融合检修手册、故障案例、图片证据与标准化作业流程，为现场人员提供可追溯、可审核的检修辅助。
          </p>
          <div class="hero-actions">
            <RouterLink class="primary-cta" to="/auth/login">进入检修工作台 <ArrowDownRight :size="18" /></RouterLink>
            <button class="secondary-cta" type="button" @click="scrollTo('#capabilities')">查看核心能力</button>
          </div>
          <dl class="hero-facts" aria-label="当前产品能力摘要">
            <div><dt>正式范围</dt><dd>Huawei SUN2000</dd></div>
            <div><dt>知识依据</dt><dd>真实手册引用</dd></div>
            <div><dt>作业边界</dt><dd>辅助建议与人工审核</dd></div>
          </dl>
        </div>
        <button class="scroll-cue" type="button" @click="scrollTo('#support-scope')">
          <span></span>继续了解
        </button>
      </section>

      <section id="support-scope" class="scope-band section-anchor">
        <div class="section-shell scope-layout">
          <div class="scope-copy scroll-reveal">
            <p class="section-kicker">SUPPORTED SCOPE</p>
            <h2>从设备型号与告警码出发<br />构建可追溯检修知识</h2>
            <p>
              当前正式生产知识范围聚焦华为 SUN2000 光伏逆变器。系统识别设备型号、告警代码、故障现象与适用文档，帮助工程师从真实资料进入排查流程。
            </p>
            <div class="scope-list">
              <span><BadgeCheck :size="18" /> 华为 SUN2000</span>
              <span><BadgeCheck :size="18" /> 设备手册与告警参考</span>
              <span><BadgeCheck :size="18" /> 故障案例与检修规程</span>
              <span><BadgeCheck :size="18" /> 来源、版本与 Trace 追踪</span>
            </div>
            <p class="expansion-note">系统采用可扩展设备知识架构，后续可按审核流程接入更多逆变器厂家与系列。</p>
          </div>
          <figure class="scope-visual scroll-reveal">
            <img :src="dualInverter" alt="光伏逆变器设备与现场" width="2048" height="1152" />
            <figcaption><span>正式知识范围</span><strong>Huawei SUN2000</strong></figcaption>
          </figure>
        </div>
      </section>

      <section id="capabilities" class="capability-stories section-anchor">
        <div class="section-shell stories-heading scroll-reveal">
          <p class="section-kicker">FIELD-READY KNOWLEDGE</p>
          <h2>知识、证据与现场作业<br />沿同一条追溯链流转</h2>
          <p>不把系统做成通用聊天窗口，而是围绕检修问题、知识依据、安全边界和执行记录组织每一步。</p>
        </div>

        <div class="story-stage">
          <article class="story-panel knowledge-story">
            <figure class="story-media">
              <img loading="lazy" decoding="async" :src="knowledgeSearch" alt="检修知识检索与来源追溯示意" width="2048" height="1152" />
            </figure>
            <div class="story-copy scroll-reveal">
              <p class="story-index">01 / 检修知识检索</p>
              <h3>检索真实资料<br />引用回到原文</h3>
              <p>通过文本问题、型号和告警码定位已审核知识片段，并返回文档、章节、页码、引用内容与 trace_id。</p>
              <ul>
                <li><FileSearch :size="18" /> 型号、告警码与故障语义联合检索</li>
                <li><BookOpenCheck :size="18" /> 引用来自真实入库文档与切片</li>
                <li><ShieldCheck :size="18" /> 证据不足时保持安全拒答边界</li>
              </ul>
            </div>
          </article>
        </div>

        <div class="story-stage">
          <article class="story-panel diagnosis-story">
            <div class="story-copy scroll-reveal">
              <p class="story-index">02 / 多模态证据与辅助诊断</p>
              <h3>把现场现象<br />变成可确认的证据</h3>
              <p>支持图片与故障描述接入，由用户确认关键信息后参与知识检索；OCR 与视觉模型按部署环境配置，不将未经确认的识别结果直接作为诊断结论。</p>
              <ul>
                <li><Camera :size="18" /> 图片、告警截图与文字描述统一归档</li>
                <li><Stethoscope :size="18" /> 输出可能原因、排查步骤与安全提醒</li>
                <li><BadgeCheck :size="18" /> 专家审核和人工修正保留完整记录</li>
              </ul>
              <p class="safety-boundary">系统输出为检修辅助建议，不能替代现场安全规程与具备资质的专业人员判断。</p>
            </div>
            <figure class="story-media light-media">
              <img loading="lazy" decoding="async" :src="faultDiagnosis" alt="光伏逆变器故障辅助诊断示意" width="2048" height="1152" />
            </figure>
          </article>
        </div>

        <div class="story-stage final-story-stage">
          <article class="story-panel workflow-story">
            <figure class="story-media">
              <img loading="lazy" decoding="async" :src="fieldEngineer" alt="现场工程师执行光伏设备检修作业示意" width="2048" height="1152" />
            </figure>
            <div class="story-copy scroll-reveal">
              <p class="story-index">03 / 标准作业与经验沉淀</p>
              <h3>让一次检修<br />形成完整业务记录</h3>
              <p>从诊断建议进入 SOP、检修任务、证据上传和专家验收，最终将处理过程沉淀到记录中心与知识审核流程。</p>
              <ul>
                <li><ClipboardCheck :size="18" /> 标准 SOP 与任务状态流转</li>
                <li><History :size="18" /> 诊断、任务、证据和 Trace 统一追踪</li>
                <li><GitBranch :size="18" /> 知识贡献与模型回答修正进入审核</li>
              </ul>
            </div>
          </article>
        </div>
      </section>

      <section class="capability-orbit section-anchor">
        <div class="section-shell">
          <div class="orbit-heading scroll-reveal">
            <p class="section-kicker">CORE CAPABILITIES</p>
            <h2>六项能力围绕现场闭环协同</h2>
            <p>选择任一能力查看业务边界。这里仅更新说明，不发送网络请求，也不会跳转到不存在的页面。</p>
          </div>
          <div class="orbit-layout">
            <div class="orbit-map" role="group" aria-label="核心能力选择">
              <div class="orbit-guide outer"></div>
              <div class="orbit-guide inner"></div>
              <button
                v-for="(item, index) in capabilities"
                :key="item.title"
                class="orbit-item"
                :class="{ active: activeCapability === index }"
                :style="{ '--angle': `${index * 60}deg` }"
                type="button"
                :aria-pressed="activeCapability === index"
                @click="activeCapability = index"
                @focus="activeCapability = index"
              >
                <component :is="item.icon" :size="20" />
                <span>{{ item.title }}</span>
              </button>
              <div class="orbit-core" aria-hidden="true"><span>EM</span><strong>现场闭环</strong><small>TRACEABLE</small></div>
            </div>
            <aside class="orbit-detail" aria-live="polite">
              <span class="detail-number">0{{ activeCapability + 1 }}</span>
              <p>{{ capabilities[activeCapability].label }}</p>
              <h3>{{ capabilities[activeCapability].title }}</h3>
              <div class="detail-rule"></div>
              <p class="detail-copy">{{ capabilities[activeCapability].description }}</p>
              <span class="detail-status">{{ capabilities[activeCapability].status }}</span>
            </aside>
          </div>
        </div>
      </section>

      <section id="workflow" class="workflow-section section-anchor">
        <div class="section-shell">
          <div class="workflow-heading scroll-reveal">
            <p class="section-kicker">STANDARD WORKFLOW</p>
            <h2>标准化检修流程</h2>
            <p>每个环节都有明确输入、责任边界和追溯记录，检修建议只有经过现场确认与专业判断后才能进入执行。</p>
          </div>
          <ol class="workflow-grid">
            <li v-for="(item, index) in workflowSteps" :key="item.title" class="workflow-step scroll-reveal">
              <span class="step-number">{{ String(index + 1).padStart(2, '0') }}</span>
              <component :is="item.icon" :size="22" />
              <h3>{{ item.title }}</h3>
              <p>{{ item.description }}</p>
            </li>
          </ol>
        </div>
      </section>

      <section class="deployment-band">
        <div class="section-shell deployment-layout scroll-reveal">
          <div>
            <p class="section-kicker">NATIVE DEPLOYMENT</p>
            <h2>面向 LoongArch 与银河麒麟原生部署</h2>
          </div>
          <p>采用 Python 虚拟环境、PostgreSQL、systemd 与 Nginx 的原生路线；具体硬件兼容性与实机表现以目标环境验收结果为准。</p>
          <div class="deployment-tags"><span>LoongArch</span><span>Kylin</span><span>FastAPI</span><span>PostgreSQL</span></div>
        </div>
      </section>

      <section id="account-guide" class="account-section section-anchor" :style="{ backgroundImage: `url(${solarField})` }">
        <div class="account-shade"></div>
        <div class="section-shell account-layout">
          <div class="account-intro scroll-reveal">
            <p class="section-kicker">ACCOUNT &amp; PERMISSION</p>
            <h2>以清晰权限<br />守护专业作业</h2>
            <p>账号由管理员统一创建并分配角色，知识审核、故障诊断、任务流转和审计记录均以服务端权限校验为准。</p>
          </div>
          <div class="account-panel scroll-reveal">
            <div class="account-panel-head">
              <p>账号说明</p>
              <h3>当前版本不开放自助注册</h3>
              <span>请联系系统管理员，按实际工作职责创建账号。</span>
            </div>
            <div class="role-grid">
              <article v-for="item in roleCards" :key="item.role">
                <strong>{{ item.role }}</strong>
                <p>{{ item.description }}</p>
              </article>
            </div>
            <RouterLink class="account-action" to="/auth/login">使用已分配账号进入系统 <ArrowDownRight :size="17" /></RouterLink>
            <RouterLink class="account-more" to="/register">查看完整账号与权限说明</RouterLink>
          </div>
        </div>
      </section>
    </main>

    <footer class="public-footer">
      <div class="public-brand footer-brand">
        <span class="brand-mark">EM</span>
        <span class="brand-copy"><strong>Energy-Maintenance</strong><small>华为 SUN2000 光伏逆变器检修</small></span>
      </div>
      <p>知识可追溯 · 诊断有边界 · 作业成闭环</p>
    </footer>
    <AppToast />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  ArrowDownRight,
  BadgeCheck,
  BookOpenCheck,
  Camera,
  ClipboardCheck,
  FileSearch,
  GitBranch,
  History,
  Layers3,
  Menu,
  ShieldCheck,
  Stethoscope,
  Wrench,
  X
} from '@lucide/vue'
import AppToast from '@/components/AppToast.vue'
import solarField from '@/assets/auth/solar-field.png'
import dualInverter from '@/assets/auth/dual-inverter.png'
import knowledgeSearch from '@/assets/auth/knowledge-search.png'
import faultDiagnosis from '@/assets/auth/fault-diagnosis.png'
import fieldEngineer from '@/assets/auth/field-engineer.png'

const mobileMenuOpen = ref(false)
const activeCapability = ref(0)
let revealObserver: IntersectionObserver | null = null

const capabilities = [
  { title: '知识检索', label: 'KNOWLEDGE RETRIEVAL', description: '基于已审核的 Huawei SUN2000 文档定位型号、告警码与检修内容，并返回真实引用。', status: '当前正式能力', icon: FileSearch },
  { title: '故障诊断', label: 'ASSISTED DIAGNOSIS', description: '结合确认后的现象与知识依据，提供可能原因、排查步骤、安全提醒和建议措施。', status: '辅助建议，不替代专业判断', icon: Stethoscope },
  { title: '多模态证据', label: 'MULTIMODAL EVIDENCE', description: '接收图片与文字故障证据，保留人工确认流程；OCR 与视觉能力按实际环境配置。', status: '证据接入与适配能力', icon: Camera },
  { title: '标准 SOP', label: 'STANDARD OPERATION', description: '把检索和诊断结果组织为可执行、可检查、有安全边界的标准作业建议。', status: '当前正式能力', icon: ClipboardCheck },
  { title: '任务闭环', label: 'MAINTENANCE WORKFLOW', description: '连接任务创建、分派、执行、证据上传、验收和记录追踪，形成完整作业链。', status: '当前正式能力', icon: Wrench },
  { title: '知识沉淀', label: 'KNOWLEDGE GOVERNANCE', description: '知识贡献、专家审核与模型回答修正进入统一治理流程，避免未经确认的信息直接发布。', status: '审核后生效', icon: Layers3 }
]

const workflowSteps = [
  { title: '故障信息输入', description: '录入型号、告警码、故障现象与现场条件。', icon: FileSearch },
  { title: '知识检索', description: '检索已审核手册、告警参考和检修案例。', icon: BookOpenCheck },
  { title: '辅助诊断', description: '形成可能原因、排查方向和安全提醒。', icon: Stethoscope },
  { title: 'SOP 推荐', description: '组织标准步骤、工具要求与风险控制。', icon: ClipboardCheck },
  { title: '检修任务', description: '关联设备、责任人、时限与处理目标。', icon: Wrench },
  { title: '证据上传', description: '保存现场图片、说明和执行过程证据。', icon: Camera },
  { title: '专家验收', description: '确认处理结果并审核知识与诊断边界。', icon: BadgeCheck },
  { title: '记录追踪', description: '通过记录中心与 Trace 回看完整链路。', icon: History }
]

const roleCards = [
  { role: '管理员', description: '维护账号、系统状态与权限策略。' },
  { role: '专家', description: '审核知识、诊断依据与经验修正。' },
  { role: '工程师', description: '执行检索、诊断、SOP 与检修任务。' },
  { role: '只读用户', description: '查看授权范围内的运行与追溯信息。' }
]

function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function scrollTo(selector: string) {
  mobileMenuOpen.value = false
  document.querySelector(selector)?.scrollIntoView({
    behavior: prefersReducedMotion() ? 'auto' : 'smooth',
    block: 'start'
  })
}

onMounted(() => {
  const targets = document.querySelectorAll('.scroll-reveal')
  if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
    targets.forEach((element) => element.classList.add('is-visible'))
  } else {
    revealObserver = new IntersectionObserver(
      (entries) => entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible')
          revealObserver?.unobserve(entry.target)
        }
      }),
      { threshold: 0.14 }
    )
    targets.forEach((element) => revealObserver?.observe(element))
  }

  if (window.location.hash) {
    window.requestAnimationFrame(() => scrollTo(window.location.hash))
  }
})

onBeforeUnmount(() => revealObserver?.disconnect())
</script>

<style scoped>
.public-home {
  --ink: #10273a;
  --navy: #061827;
  --blue: #176cac;
  --cyan: #69c8ee;
  --green: #1f8b57;
  --amber: #d97706;
  --line: #cbdbe5;
  min-height: 100vh;
  overflow-x: clip;
  background: #f4f7f9;
  color: var(--ink);
}

.public-nav {
  position: fixed;
  inset: 0 0 auto;
  z-index: 60;
  display: grid;
  grid-template-columns: minmax(230px, 1fr) auto minmax(150px, 1fr);
  align-items: center;
  height: 72px;
  padding: 0 4vw;
  border-bottom: 1px solid rgb(255 255 255 / 18%);
  background: rgb(4 20 33 / 80%);
  color: #fff;
  backdrop-filter: blur(14px);
}

.public-brand {
  display: inline-flex;
  align-items: center;
  justify-self: start;
  gap: 12px;
  min-width: 0;
  text-align: left;
}

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  flex: none;
  place-items: center;
  border: 1px solid rgb(255 255 255 / 34%);
  background: var(--blue);
  color: #fff;
  font-weight: 900;
}

.brand-copy strong,
.brand-copy small {
  display: block;
  letter-spacing: 0;
}

.brand-copy strong { font-size: 15px; }
.brand-copy small { margin-top: 2px; color: #b4cad8; font-size: 11px; }

.public-links {
  display: flex;
  align-items: center;
  gap: 6px;
  justify-self: center;
}

.public-links button {
  min-height: 38px;
  padding: 0 13px;
  border-bottom: 2px solid transparent;
  color: #d9e8f2;
  font-size: 13px;
  font-weight: 800;
}

.public-links button:hover,
.public-links button:focus-visible {
  border-bottom-color: var(--cyan);
  color: #fff;
  outline: none;
}

.nav-login {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  justify-self: end;
  gap: 8px;
  border: 1px solid rgb(255 255 255 / 64%);
  padding: 0 16px;
  color: #fff;
  font-size: 13px;
  font-weight: 900;
}

.nav-login:hover,
.nav-login:focus-visible {
  border-color: var(--cyan);
  background: #fff;
  color: #0a314d;
  outline: none;
}

.menu-toggle { display: none; }

.hero-section {
  position: relative;
  display: flex;
  min-height: 92svh;
  align-items: center;
  overflow: hidden;
  padding: 116px 7vw 72px;
  background-position: center;
  background-size: cover;
  color: #fff;
}

.hero-shade {
  position: absolute;
  inset: 0;
  background: rgb(2 15 25 / 66%);
}

.hero-content {
  position: relative;
  z-index: 1;
  width: min(820px, 100%);
}

.eyebrow,
.section-kicker,
.story-index {
  margin: 0;
  color: var(--cyan);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0;
}

.eyebrow { display: flex; align-items: center; gap: 12px; }
.eyebrow span { width: 42px; height: 2px; background: var(--cyan); }

.hero-content h1 {
  margin: 22px 0 0;
  max-width: 800px;
  font-size: 72px;
  line-height: 1.06;
  letter-spacing: 0;
  text-wrap: balance;
}

.hero-statement {
  margin: 26px 0 0;
  color: #fff;
  font-size: 24px;
  font-weight: 800;
}

.hero-copy {
  max-width: 670px;
  margin: 14px 0 0;
  color: #d7e6ef;
  font-size: 17px;
  line-height: 1.85;
}

.hero-actions { display: flex; gap: 12px; margin-top: 32px; }
.primary-cta,
.secondary-cta {
  display: inline-flex;
  min-height: 50px;
  align-items: center;
  justify-content: center;
  gap: 9px;
  padding: 0 22px;
  font-weight: 900;
}
.primary-cta { background: #fff; color: #0a314d; }
.secondary-cta { border: 1px solid rgb(255 255 255 / 65%); color: #fff; }
.primary-cta:hover,
.primary-cta:focus-visible,
.secondary-cta:hover,
.secondary-cta:focus-visible { outline: 3px solid rgb(105 200 238 / 45%); outline-offset: 3px; }

.hero-facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  max-width: 760px;
  margin: 38px 0 0;
  border-top: 1px solid rgb(255 255 255 / 35%);
  border-bottom: 1px solid rgb(255 255 255 / 35%);
}
.hero-facts div { padding: 15px 18px 15px 0; }
.hero-facts div + div { padding-left: 18px; border-left: 1px solid rgb(255 255 255 / 25%); }
.hero-facts dt { color: #9fc1d4; font-size: 11px; font-weight: 800; }
.hero-facts dd { margin: 6px 0 0; color: #fff; font-size: 14px; font-weight: 900; }

.scroll-cue {
  position: absolute;
  z-index: 2;
  right: 4vw;
  bottom: 22px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #dceaf2;
  font-size: 11px;
  font-weight: 800;
}
.scroll-cue span { width: 52px; height: 1px; background: #fff; }

.section-shell { width: min(1180px, calc(100% - 40px)); margin-inline: auto; }
.section-anchor { scroll-margin-top: 72px; }

.scope-band { padding: 92px 0; background: #f4f7f9; }
.scope-layout { display: grid; grid-template-columns: minmax(0, .9fr) minmax(420px, 1.1fr); align-items: center; gap: 70px; }
.scope-copy h2,
.stories-heading h2,
.orbit-heading h2,
.workflow-heading h2,
.deployment-layout h2,
.account-intro h2 {
  margin: 16px 0 0;
  color: var(--ink);
  font-size: 46px;
  line-height: 1.12;
  letter-spacing: 0;
  text-wrap: balance;
}
.scope-copy > p:not(.section-kicker) { margin: 24px 0 0; color: #60798b; font-size: 15px; line-height: 1.9; }
.scope-list { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin-top: 28px; border: 1px solid var(--line); background: var(--line); }
.scope-list span { display: flex; min-height: 58px; align-items: center; gap: 10px; background: #fff; padding: 12px 14px; color: #31536b; font-size: 13px; font-weight: 800; }
.scope-list svg { flex: none; color: var(--green); }
.expansion-note { padding-left: 14px; border-left: 3px solid var(--amber); }
.scope-visual { position: relative; margin: 0; aspect-ratio: 16 / 10; overflow: hidden; background: #dce8ef; }
.scope-visual img { width: 100%; height: 100%; object-fit: cover; }
.scope-visual figcaption { position: absolute; right: 0; bottom: 0; display: grid; min-width: 230px; background: rgb(4 24 39 / 91%); padding: 15px 18px; color: #fff; }
.scope-visual figcaption span { color: #9fc2d7; font-size: 10px; font-weight: 800; }
.scope-visual figcaption strong { margin-top: 4px; font-size: 15px; }

.capability-stories { padding-top: 88px; background: #e8eff3; }
.stories-heading { padding-bottom: 52px; }
.stories-heading > p:last-child,
.orbit-heading > p:last-child,
.workflow-heading > p:last-child { max-width: 700px; margin: 20px 0 0; color: #637b8c; font-size: 15px; line-height: 1.8; }
.story-stage { position: relative; height: 126svh; }
.final-story-stage { height: 112svh; }
.story-panel {
  position: sticky;
  top: 72px;
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(380px, .85fr);
  min-height: calc(100svh - 72px);
  align-items: center;
  gap: 72px;
  overflow: hidden;
  padding: 64px max(5vw, calc((100vw - 1180px) / 2));
  box-shadow: 0 -20px 54px rgb(3 18 30 / 16%);
}
.knowledge-story { background: #071b2c; color: #fff; }
.diagnosis-story { grid-template-columns: minmax(380px, .85fr) minmax(0, 1.15fr); background: #f7f9fa; }
.workflow-story { background: #103e43; color: #fff; }
.story-media { margin: 0; aspect-ratio: 16 / 10; overflow: hidden; background: #dbe6ec; }
.story-media img { width: 100%; height: 100%; object-fit: cover; transition: transform 500ms ease; }
.story-panel:hover .story-media img { transform: scale(1.02); }
.light-media { border: 12px solid #fff; box-shadow: 0 22px 54px rgb(16 39 58 / 15%); }
.story-copy h3 { margin: 15px 0 0; font-size: 48px; line-height: 1.08; letter-spacing: 0; text-wrap: balance; }
.story-copy > p:not(.story-index, .safety-boundary) { margin: 24px 0 0; color: #bdd1df; font-size: 15px; line-height: 1.9; }
.diagnosis-story .story-copy > p:not(.story-index, .safety-boundary) { color: #60798b; }
.story-copy ul { display: grid; gap: 0; margin: 28px 0 0; padding: 0; border-top: 1px solid rgb(255 255 255 / 24%); list-style: none; }
.diagnosis-story .story-copy ul { border-color: var(--line); }
.story-copy li { display: flex; align-items: center; gap: 10px; padding: 13px 0; border-bottom: 1px solid rgb(255 255 255 / 18%); font-size: 13px; font-weight: 800; }
.diagnosis-story .story-copy li { border-color: var(--line); color: #31536b; }
.story-copy li svg { flex: none; color: var(--cyan); }
.diagnosis-story .story-copy li svg { color: var(--blue); }
.safety-boundary { margin: 22px 0 0; border-left: 3px solid var(--amber); background: #fff5e8; padding: 12px 14px; color: #7c4a14; font-size: 12px; line-height: 1.75; }

.capability-orbit { padding: 104px 0; background: #f4f7f9; }
.orbit-heading { max-width: 760px; }
.orbit-layout { display: grid; grid-template-columns: minmax(540px, 1fr) minmax(310px, .62fr); align-items: center; gap: 80px; margin-top: 58px; }
.orbit-map { position: relative; width: min(560px, 100%); aspect-ratio: 1; margin-inline: auto; }
.orbit-guide { position: absolute; border: 1px solid rgb(23 108 172 / 23%); border-radius: 50%; pointer-events: none; }
.orbit-guide.outer { inset: 8%; }
.orbit-guide.inner { inset: 29%; border-style: dashed; }
.orbit-item {
  --radius: 218px;
  position: absolute;
  top: 50%;
  left: 50%;
  display: grid;
  width: 108px;
  height: 108px;
  margin: -54px;
  place-items: center;
  align-content: center;
  gap: 8px;
  border: 1px solid #b8cedb;
  border-radius: 50%;
  background: #fff;
  color: #24465e;
  box-shadow: 0 12px 30px rgb(20 58 83 / 10%);
  transform: rotate(var(--angle)) translateY(calc(var(--radius) * -1)) rotate(calc(var(--angle) * -1));
}
.orbit-item span { font-size: 13px; font-weight: 900; }
.orbit-item svg { color: var(--blue); }
.orbit-item:hover,
.orbit-item:focus-visible,
.orbit-item.active { border-color: var(--blue); background: var(--blue); color: #fff; outline: none; box-shadow: 0 15px 38px rgb(23 108 172 / 28%); }
.orbit-item:hover svg,
.orbit-item:focus-visible svg,
.orbit-item.active svg { color: #fff; }
.orbit-core { position: absolute; inset: 34%; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 50%; background: var(--navy); color: #fff; box-shadow: 0 20px 48px rgb(6 24 39 / 26%); }
.orbit-core span { color: var(--cyan); font-size: 24px; font-weight: 900; }
.orbit-core strong { margin-top: 5px; font-size: 15px; }
.orbit-core small { margin-top: 4px; color: #8faabc; font-size: 8px; }
.orbit-detail { position: relative; min-height: 330px; padding: 36px 0 36px 40px; border-left: 1px solid #b9cedb; }
.detail-number { position: absolute; top: -20px; right: 0; color: rgb(23 108 172 / 9%); font-size: 112px; line-height: 1; font-weight: 900; }
.orbit-detail > p:first-of-type { position: relative; color: var(--blue); font-size: 10px; font-weight: 900; }
.orbit-detail h3 { position: relative; margin: 14px 0 0; font-size: 44px; line-height: 1.12; }
.detail-rule { width: 56px; height: 3px; margin-top: 22px; background: var(--blue); }
.detail-copy { min-height: 86px; margin: 22px 0 0; color: #60798b; font-size: 15px; line-height: 1.85; }
.detail-status { display: inline-flex; margin-top: 22px; border: 1px solid #b8cedb; background: #fff; padding: 8px 12px; color: #31536b; font-size: 11px; font-weight: 800; }

.workflow-section { padding: 102px 0; background: #0c304d; color: #fff; }
.workflow-heading h2 { color: #fff; }
.workflow-heading > p:last-child { color: #b9cfdd; }
.workflow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 54px 0 0; padding: 0; border-top: 1px solid rgb(255 255 255 / 26%); list-style: none; }
.workflow-step { position: relative; min-height: 230px; padding: 28px 24px; border-right: 1px solid rgb(255 255 255 / 20%); border-bottom: 1px solid rgb(255 255 255 / 20%); }
.workflow-step:nth-child(4n + 1) { border-left: 1px solid rgb(255 255 255 / 20%); }
.workflow-step svg { margin-top: 30px; color: var(--cyan); }
.step-number { color: #7fa3b9; font-size: 11px; font-weight: 900; }
.workflow-step h3 { margin: 13px 0 0; font-size: 18px; }
.workflow-step p { margin: 10px 0 0; color: #b6cbd8; font-size: 12px; line-height: 1.7; }

.deployment-band { padding: 66px 0; border-bottom: 1px solid #d3e0e8; background: #eef4f7; }
.deployment-layout { display: grid; grid-template-columns: 1fr .9fr; align-items: center; gap: 24px 70px; }
.deployment-layout h2 { font-size: 36px; }
.deployment-layout > p { margin: 0; color: #60798b; font-size: 14px; line-height: 1.85; }
.deployment-tags { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; }
.deployment-tags span { border: 1px solid #bdd0dc; background: #fff; padding: 8px 12px; color: #31536b; font-size: 11px; font-weight: 900; }

.account-section { position: relative; min-height: 720px; padding: 96px 0; background-position: center; background-size: cover; color: #fff; }
.account-shade { position: absolute; inset: 0; background: rgb(2 17 28 / 73%); }
.account-layout { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) minmax(420px, 540px); align-items: center; gap: 90px; }
.account-intro h2 { color: #fff; }
.account-intro > p:last-child { max-width: 620px; margin: 24px 0 0; color: #ccdee9; font-size: 15px; line-height: 1.9; }
.account-panel { border-top: 3px solid var(--cyan); background: rgb(255 255 255 / 96%); padding: 34px; color: var(--ink); box-shadow: 0 28px 72px rgb(0 0 0 / 32%); }
.account-panel-head > p { margin: 0; color: var(--blue); font-size: 11px; font-weight: 900; }
.account-panel-head h3 { margin: 8px 0 0; font-size: 27px; }
.account-panel-head span { display: block; margin-top: 8px; color: #687f90; font-size: 12px; }
.role-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; margin-top: 24px; border: 1px solid #d4e1e8; background: #d4e1e8; }
.role-grid article { min-height: 105px; background: #fff; padding: 15px; }
.role-grid strong { font-size: 14px; }
.role-grid p { margin: 7px 0 0; color: #667e8f; font-size: 11px; line-height: 1.65; }
.account-action { display: flex; min-height: 48px; align-items: center; justify-content: center; gap: 9px; margin-top: 20px; background: var(--blue); color: #fff; font-size: 13px; font-weight: 900; }
.account-more { display: block; margin-top: 14px; text-align: center; color: var(--blue); font-size: 12px; font-weight: 800; }
.account-action:focus-visible,
.account-more:focus-visible { outline: 3px solid rgb(23 108 172 / 28%); outline-offset: 3px; }

.public-footer { display: flex; align-items: center; justify-content: space-between; gap: 30px; padding: 28px 5vw; background: #03111d; color: #fff; }
.public-footer p { margin: 0; color: #8fa8b9; font-size: 11px; font-weight: 800; }

.reveal-on-load { animation: reveal-up 620ms ease both; }
.scroll-reveal { opacity: 0; transform: translateY(28px); transition: opacity 620ms ease, transform 620ms ease; }
.scroll-reveal.is-visible { opacity: 1; transform: none; }
@keyframes reveal-up { from { opacity: 0; transform: translateY(28px); } to { opacity: 1; transform: none; } }

@media (max-width: 1100px) {
  .public-nav { grid-template-columns: 1fr auto; }
  .public-links { display: none; }
  .nav-login { margin-right: 52px; }
  .menu-toggle { position: absolute; right: 4vw; display: grid; width: 40px; height: 40px; place-items: center; color: #fff; }
  .public-nav.menu-open .public-links { position: absolute; inset: 72px 0 auto; display: grid; gap: 0; border-bottom: 1px solid rgb(255 255 255 / 18%); background: #071d2f; padding: 10px 4vw 14px; }
  .public-nav.menu-open .public-links button { justify-self: stretch; text-align: left; }
  .scope-layout { grid-template-columns: 1fr; }
  .scope-visual { max-width: 820px; }
  .story-panel,
  .diagnosis-story { grid-template-columns: 1fr; gap: 38px; padding-top: 52px; padding-bottom: 52px; }
  .story-media { max-height: 48svh; }
  .diagnosis-story .story-copy { order: 2; }
  .diagnosis-story .story-media { order: 1; }
  .orbit-layout { grid-template-columns: 1fr; }
  .orbit-detail { width: min(620px, 100%); margin-inline: auto; }
  .workflow-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workflow-step:nth-child(odd) { border-left: 1px solid rgb(255 255 255 / 20%); }
  .account-layout { grid-template-columns: 1fr; }
  .account-panel { width: min(620px, 100%); }
}

@media (max-width: 760px) {
  .public-nav { height: 66px; padding-inline: 18px; }
  .brand-copy small { display: none; }
  .nav-login { min-height: 38px; margin-right: 48px; padding-inline: 12px; }
  .menu-toggle { right: 18px; }
  .public-nav.menu-open .public-links { top: 66px; padding-inline: 18px; }
  .hero-section { min-height: 90svh; padding: 104px 20px 66px; background-position: 58% center; }
  .hero-content h1 { font-size: 44px; }
  .hero-statement { font-size: 20px; }
  .hero-copy { font-size: 15px; }
  .hero-actions { align-items: stretch; flex-direction: column; }
  .hero-facts { grid-template-columns: 1fr; }
  .hero-facts div { padding: 11px 0; }
  .hero-facts div + div { padding-left: 0; border-top: 1px solid rgb(255 255 255 / 22%); border-left: 0; }
  .scroll-cue { display: none; }
  .section-shell { width: min(100% - 32px, 1180px); }
  .scope-band,
  .capability-orbit,
  .workflow-section { padding: 76px 0; }
  .scope-copy h2,
  .stories-heading h2,
  .orbit-heading h2,
  .workflow-heading h2,
  .account-intro h2 { font-size: 34px; }
  .scope-list { grid-template-columns: 1fr; }
  .scope-visual { aspect-ratio: 4 / 3; }
  .scope-visual figcaption { min-width: 190px; }
  .capability-stories { padding-top: 72px; }
  .story-stage,
  .final-story-stage { height: auto; }
  .story-panel,
  .diagnosis-story { position: relative; top: auto; min-height: auto; gap: 30px; padding: 56px 16px; }
  .story-copy h3 { font-size: 36px; }
  .story-media { aspect-ratio: 4 / 3; }
  .orbit-map { display: grid; width: 100%; aspect-ratio: auto; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
  .orbit-guide,
  .orbit-core { display: none; }
  .orbit-item { position: static; width: auto; height: 94px; margin: 0; border-radius: 4px; transform: none; }
  .orbit-detail { min-height: 300px; padding-left: 22px; }
  .orbit-detail h3 { font-size: 36px; }
  .detail-number { font-size: 86px; }
  .workflow-grid { grid-template-columns: 1fr; }
  .workflow-step,
  .workflow-step:nth-child(n) { min-height: 190px; border-left: 1px solid rgb(255 255 255 / 20%); }
  .deployment-layout { grid-template-columns: 1fr; }
  .deployment-layout h2 { font-size: 30px; }
  .deployment-tags { grid-column: auto; }
  .account-section { min-height: auto; padding: 78px 0; }
  .account-layout { gap: 42px; }
  .account-panel { padding: 24px; }
  .role-grid { grid-template-columns: 1fr; }
  .public-footer { align-items: flex-start; flex-direction: column; padding-inline: 20px; }
}

@media (prefers-reduced-motion: reduce) {
  .reveal-on-load { animation: none; }
  .scroll-reveal { opacity: 1; transform: none; transition: none; }
  .story-media img { transition: none; }
  .story-panel:hover .story-media img { transform: none; }
}
</style>
