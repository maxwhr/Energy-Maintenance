<template>
  <PageFrame
    title="系统状态"
    code="SYSTEM / STATUS"
    description="查看 FastAPI 服务、PostgreSQL 连接、核心业务表计数与模型网关配置状态。"
  >
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadStatus">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 lg:grid-cols-4">
      <DataPanel v-for="item in cards" :key="item.label" :title="item.label">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <div class="truncate text-2xl font-black text-white">{{ item.value }}</div>
            <div class="mt-2 font-mono text-xs text-slate-400">{{ item.detail }}</div>
          </div>
          <StatusPill :value="item.status" :label="item.statusLabel" />
        </div>
      </DataPanel>
    </div>

    <div class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
      <DataPanel title="PostgreSQL 连接检查" subtitle="由后端 /api/system/status 实时执行 SELECT 1 与核心表计数。">
        <div class="grid gap-3 md:grid-cols-2">
          <div v-for="item in databaseDetails" :key="item.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
            <div class="text-xs font-bold text-slate-400">{{ item.label }}</div>
            <div class="mt-1 break-words text-sm font-bold text-white">{{ item.value }}</div>
          </div>
        </div>
        <div
          v-if="status?.database_error"
          class="mt-4 rounded-md border border-red-400/30 bg-red-500/10 p-3 text-sm leading-6 text-red-200"
        >
          数据库连接异常：{{ status.database_error }}
        </div>
      </DataPanel>

      <DataPanel title="运行计数">
        <div class="space-y-3">
          <div v-for="item in countItems" :key="item.label" class="flex items-center justify-between gap-3">
            <span class="text-sm text-slate-300">{{ item.label }}</span>
            <span class="font-mono text-sm font-black text-cyan-100">{{ item.value }}</span>
          </div>
        </div>
      </DataPanel>
    </div>

    <DataPanel title="安全配置" subtitle="展示后端脱敏后的安全配置状态，不显示密钥、令牌、数据库口令或本地文件路径。">
      <div class="grid gap-3 md:grid-cols-3">
        <div v-for="item in securityDetails" :key="item.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
          <div class="text-xs font-bold text-slate-400">{{ item.label }}</div>
          <div class="mt-1 break-words text-sm font-bold text-white">{{ item.value }}</div>
        </div>
      </div>
      <div v-if="securityWarnings.length" class="mt-4 rounded-md border border-amber-400/30 bg-amber-500/10 p-3">
        <div class="text-xs font-black text-amber-100">安全提示</div>
        <ul class="mt-2 space-y-1 text-xs leading-5 text-amber-100">
          <li v-for="warning in securityWarnings" :key="warning">{{ warning }}</li>
        </ul>
      </div>
    </DataPanel>

    <div class="grid gap-4 lg:grid-cols-2">
      <DataPanel title="业务统计概览">
        <div v-if="statistics" class="grid gap-3 md:grid-cols-2">
          <section v-for="section in statisticSections" :key="section.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
            <h3 class="text-sm font-black text-white">{{ section.label }}</h3>
            <div class="mt-3 space-y-2">
              <div v-for="item in section.items" :key="item.key" class="flex items-center justify-between gap-3 text-xs">
                <span class="text-slate-400">{{ item.label }}</span>
                <span class="font-mono text-slate-100">{{ item.value }}</span>
              </div>
            </div>
          </section>
        </div>
        <EmptyState v-else text="尚未读取到业务统计" />
      </DataPanel>

      <DataPanel title="模型网关">
        <div v-if="modelGateway" class="space-y-3">
          <article v-for="provider in modelGateway.providers" :key="provider.provider" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex items-start justify-between gap-3">
              <div>
                <div class="font-black text-white">{{ formatProviderName(provider.provider) }}</div>
                <div class="mt-1 text-xs text-slate-400">
                  {{ formatProviderMessage(provider.provider, provider.availability_status, provider.message) }}
                </div>
                <div class="mt-2 font-mono text-xs text-slate-500">
                  {{ provider.provider }} / {{ provider.model_name || '未配置模型名称' }}
                </div>
              </div>
              <StatusPill :value="provider.availability_status || (provider.available ? 'available' : 'unavailable')" />
            </div>
          </article>
        </div>
        <EmptyState v-else text="尚未读取到模型网关状态" />
      </DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RefreshCcw } from '@lucide/vue'
import { getModelGatewayStatusApi, getSystemStatisticsApi, getSystemStatusApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import type { ModelGatewayStatus, SystemStatistics, SystemStatus } from '@/types'
import {
  formatMetricLabel,
  formatMetricSectionLabel,
  formatProviderMessage,
  formatProviderName,
  formatStatusLabel
} from '@/utils/display'

const status = ref<SystemStatus | null>(null)
const statistics = ref<SystemStatistics | null>(null)
const modelGateway = ref<ModelGatewayStatus | null>(null)
const loading = ref(false)
const error = ref('')

const cards = computed(() => [
  {
    label: '后端服务',
    value: formatStatusLabel(status.value?.service_status || status.value?.status),
    status: status.value?.service_status === 'running' || status.value?.status === 'running' ? 'online' : 'offline',
    statusLabel: status.value?.service_status === 'running' || status.value?.status === 'running' ? '运行中' : '异常',
    detail: '/api/system/status'
  },
  {
    label: '数据库',
    value: formatStatusLabel(status.value?.database_status),
    status: status.value?.database_status === 'online' ? 'online' : 'offline',
    statusLabel: status.value?.database_status === 'online' ? '在线' : '离线',
    detail: 'PostgreSQL'
  },
  {
    label: '知识文档',
    value: String(status.value?.document_count ?? 0),
    status: 'info',
    statusLabel: '文档',
    detail: 'knowledge_documents'
  },
  {
    label: '知识切片',
    value: String(status.value?.chunk_count ?? 0),
    status: 'info',
    statusLabel: '切片',
    detail: 'knowledge_chunks'
  }
])

const databaseDetails = computed(() => [
  { label: '连接状态', value: formatStatusLabel(status.value?.database_status) },
  { label: '检查时间', value: formatTime(status.value?.database_checked_at) },
  { label: '响应延迟', value: status.value?.database_latency_ms == null ? '-' : `${status.value.database_latency_ms} ms` },
  { label: '错误类型', value: status.value?.database_error || '无' }
])

const securityDetails = computed(() => {
  const security = status.value?.security ?? {}
  return [
    { label: '安全校验', value: formatStatusLabel(readSecurityValue(security, 'status')) },
    { label: '运行环境', value: readSecurityValue(security, 'app_env') },
    { label: '调试模式', value: formatBoolean(readRawSecurityValue(security, 'debug_enabled')) },
    { label: '生产强校验', value: formatBoolean(readRawSecurityValue(security, 'production_guard_enabled')) },
    { label: 'CORS 来源', value: readSecurityValue(security, 'cors_origin_policy') },
    { label: '请求体限制', value: formatBoolean(readRawSecurityValue(security, 'request_size_limit_enabled')) },
    { label: '限流保护', value: formatBoolean(readRawSecurityValue(security, 'rate_limit_enabled')) },
    { label: '外部真实调用', value: formatStatusLabel(readSecurityValue(security, 'external_real_call_status')) },
    { label: '日志目录', value: formatBoolean(readRawSecurityValue(security, 'log_dir_configured')) },
    { label: 'DashVector Key', value: formatConfigured(readRawSecurityValue(security, 'dashvector_key_configured')) },
    { label: 'Embedding Key', value: formatConfigured(readRawSecurityValue(security, 'embedding_key_configured')) },
    { label: '云端模型 Key', value: formatConfigured(readRawSecurityValue(security, 'cloud_llm_key_configured')) },
    { label: 'MIMO Key', value: formatConfigured(readRawSecurityValue(security, 'mimo_key_configured')) },
    { label: 'OCR API Key', value: formatConfigured(readRawSecurityValue(security, 'ocr_key_configured')) },
    { label: '本地模型', value: formatBoolean(readRawSecurityValue(security, 'local_llm_enabled')) }
  ]
})

const securityWarnings = computed(() => {
  const security = status.value?.security ?? {}
  const warnings = readRawSecurityValue(security, 'warnings')
  return Array.isArray(warnings) ? warnings.map((item) => formatSecurityWarning(String(item))) : []
})

const countItems = computed(() => [
  { label: '文档', value: status.value?.document_count ?? 0 },
  { label: '切片', value: status.value?.chunk_count ?? 0 },
  { label: '问答记录', value: status.value?.qa_record_count ?? 0 },
  { label: '诊断记录', value: status.value?.diagnosis_record_count ?? 0 },
  { label: '检修任务', value: status.value?.maintenance_task_count ?? 0 },
  { label: '媒体附件', value: status.value?.media_count ?? 0 },
  { label: 'SOP 模板', value: status.value?.sop_template_count ?? 0 }
])

const statisticSections = computed(() => {
  if (!statistics.value) return []
  return Object.entries(statistics.value)
    .filter(([, value]) => value && typeof value === 'object' && !Array.isArray(value))
    .map(([key, value]) => ({
      label: formatMetricSectionLabel(key),
      technicalKey: key,
      items: Object.entries(value as Record<string, unknown>).map(([key, itemValue]) => ({
        key,
        label: formatMetricLabel(key),
        value: String(itemValue ?? '-')
      }))
    }))
})

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const [systemStatus, systemStatistics, gateway] = await Promise.all([
      getSystemStatusApi(),
      getSystemStatisticsApi(),
      getModelGatewayStatusApi()
    ])
    status.value = systemStatus
    statistics.value = systemStatistics
    modelGateway.value = gateway
  } catch (err) {
    error.value = err instanceof Error ? err.message : '系统状态读取失败'
    status.value = null
    statistics.value = null
    modelGateway.value = null
  } finally {
    loading.value = false
  }
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function readSecurityValue(source: Record<string, unknown>, key: string) {
  return String(source[key] ?? '-')
}

function readRawSecurityValue(source: Record<string, unknown>, key: string) {
  return source[key]
}

function formatBoolean(value: unknown) {
  if (value === true) return '已启用'
  if (value === false) return '未启用'
  return String(value ?? '-')
}

function formatConfigured(value: unknown) {
  if (value === true) return '已配置（不显示值）'
  if (value === false) return '未配置'
  return String(value ?? '-')
}

function formatSecurityWarning(value: string) {
  const knownWarnings: Record<string, string> = {
    'ADMIN_PASSWORD is not configured; local scripts may use development fallback': '管理员初始密码未通过环境变量配置；本地脚本可能使用开发兜底值。',
    'SECRET_KEY is missing or uses a placeholder value': 'SECRET_KEY 仍为空或占位值，生产环境必须替换为高强度随机值。'
  }
  return knownWarnings[value] ?? value
}

onMounted(loadStatus)
</script>
