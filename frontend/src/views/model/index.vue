<template>
  <PageFrame title="模型服务" code="MODEL / GATEWAY" description="查看后端模型网关状态、执行连通性测试、发起受控对话并追溯调用日志。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadAll">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel title="网关状态">
        <div v-if="status" class="space-y-3 text-sm text-slate-300">
          <div class="rounded-md bg-white/[0.03] p-3">
            默认模型服务：{{ formatProviderName(status.default_provider) }}
            <span class="ml-2 font-mono text-xs text-slate-500">{{ status.default_provider }}</span>
          </div>
          <div class="rounded-md bg-white/[0.03] p-3">超时：{{ status.timeout_seconds }} 秒</div>
          <div class="rounded-md bg-white/[0.03] p-3">日志：{{ status.logging_enabled ? '启用' : '停用' }}</div>
        </div>
        <EmptyState v-else text="尚未读取模型网关状态" />
      </DataPanel>

      <DataPanel title="模型服务提供方">
        <div v-if="status?.providers?.length" class="space-y-3">
          <article v-for="provider in status.providers" :key="provider.provider" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
            <div class="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h3 class="font-black text-white">{{ formatProviderName(provider.provider) }}</h3>
                <p class="mt-1 text-xs text-slate-400">
                  {{ formatProviderMessage(provider.provider, provider.availability_status, provider.message) }}
                </p>
                <p class="mt-1 font-mono text-xs text-slate-500">{{ provider.provider }} / {{ provider.model_name || '未配置模型名称' }}</p>
                <p class="mt-1 text-xs text-slate-500">接口密钥：{{ provider.api_key_configured ? '已配置' : '未配置' }}</p>
                <div v-if="provider.provider === 'local_llama_cpp'" class="mt-2 grid gap-1 text-xs text-slate-500 sm:grid-cols-2">
                  <span>API 类型：{{ provider.api_type || '-' }}</span>
                  <span>Base URL：{{ provider.base_url_configured ? '已配置' : '未配置' }}</span>
                  <span>健康检查：{{ provider.health_path || '-' }}</span>
                  <span>延迟：{{ provider.latency_ms == null ? '-' : `${provider.latency_ms} ms` }}</span>
                  <span class="sm:col-span-2">状态摘要：{{ provider.error_summary || provider.message }}</span>
                </div>
              </div>
              <StatusPill :value="provider.availability_status || (provider.available ? 'available' : 'unavailable')" />
            </div>
          </article>
        </div>
        <EmptyState v-else text="暂无模型服务提供方配置" />
      </DataPanel>
    </div>

    <div class="grid gap-4 xl:grid-cols-2">
      <DataPanel title="连通性测试">
        <form class="grid gap-3" @submit.prevent="testGateway">
          <select v-model="testForm.provider" class="scada-input">
            <option value="">默认模型服务</option>
            <option value="rule_based">规则兜底模型</option>
            <option value="local_llama_cpp">本地 llama.cpp 模型</option>
            <option value="cloud_openai">云端 OpenAI 兼容模型</option>
          </select>
          <input v-model.trim="testForm.prompt" class="scada-input" required placeholder="输入测试内容，例如：返回网关连通状态" />
          <button class="scada-button primary" type="submit" :disabled="testing">测试调用</button>
        </form>
        <pre v-if="testResult" class="mt-4 max-h-80 overflow-auto rounded-md bg-black/30 p-4 text-xs leading-6 text-slate-300">{{ JSON.stringify(testResult, null, 2) }}</pre>
      </DataPanel>

      <DataPanel title="受控对话调用">
        <form class="grid gap-3" @submit.prevent="chatGateway">
          <select v-model="chatForm.provider" class="scada-input">
            <option value="">默认模型服务</option>
            <option value="rule_based">规则兜底模型</option>
            <option value="local_llama_cpp">本地 llama.cpp 模型</option>
            <option value="cloud_openai">云端 OpenAI 兼容模型</option>
          </select>
          <textarea v-model.trim="chatForm.prompt" class="scada-input min-h-28" required placeholder="输入受控对话测试内容，不显示任何接口密钥"></textarea>
          <button class="scada-button primary" type="submit" :disabled="chatting">发起对话</button>
        </form>
        <pre v-if="chatResult" class="mt-4 max-h-80 overflow-auto rounded-md bg-black/30 p-4 text-xs leading-6 text-slate-300">{{ JSON.stringify(chatResult, null, 2) }}</pre>
      </DataPanel>
    </div>

    <DataPanel title="调用日志">
      <div v-if="logs.length" class="space-y-3">
        <article v-for="log in logs" :key="String(log.id)" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h3 class="font-black text-white">{{ formatProviderName(log.provider as string) }} / {{ log.model_name || '-' }}</h3>
              <p class="mt-1 text-xs text-slate-400">trace_id: {{ log.trace_id || '-' }} / {{ log.call_type || '-' }} / {{ formatTime(log.created_at as string) }}</p>
              <p class="mt-2 line-clamp-2 text-sm leading-6 text-slate-300">{{ log.error_message || log.response || log.prompt || '无摘要' }}</p>
            </div>
            <div class="flex flex-wrap gap-2">
              <StatusPill :value="log.success ? 'completed' : 'failed'" :label="log.success ? '成功' : '失败'" />
              <button class="scada-button !min-h-8 !px-3" type="button" @click="loadLogDetail(String(log.id))">详情</button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无模型调用日志" />
    </DataPanel>

    <DataPanel v-if="logDetail" title="日志详情">
      <div class="grid gap-3 md:grid-cols-3">
        <div v-for="item in logDetailRows" :key="item.label" class="rounded-md border border-slate-600/20 bg-black/20 p-3">
          <div class="text-xs font-bold text-slate-400">{{ item.label }}</div>
          <div class="mt-1 break-words text-sm font-bold text-white">{{ item.value }}</div>
        </div>
      </div>
      <div class="mt-4 grid gap-4 lg:grid-cols-2">
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">请求内容</h3>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">{{ logDetail.prompt || '-' }}</p>
        </section>
        <section class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <h3 class="text-sm font-black text-white">响应内容</h3>
          <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">{{ logDetail.response || logDetail.error_message || '-' }}</p>
        </section>
      </div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RefreshCcw } from '@lucide/vue'
import { chatModelGatewayApi, getModelCallLogApi, getModelCallLogsApi, getModelGatewayStatusApi, testModelGatewayApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import type { ModelGatewayResponse, ModelGatewayStatus } from '@/types'
import { formatProviderMessage, formatProviderName } from '@/utils/display'

const status = ref<ModelGatewayStatus | null>(null)
const testResult = ref<ModelGatewayResponse | null>(null)
const chatResult = ref<ModelGatewayResponse | null>(null)
const logs = ref<Record<string, unknown>[]>([])
const logDetail = ref<Record<string, unknown> | null>(null)
const loading = ref(false)
const testing = ref(false)
const chatting = ref(false)
const error = ref('')
const testForm = reactive({ provider: '', prompt: '请返回模型网关连通状态。' })
const chatForm = reactive({ provider: '', prompt: '请用一句话说明光伏逆变器检修问答模块的作用。' })

const logDetailRows = computed(() => {
  if (!logDetail.value) return []
  return [
    { label: 'trace_id', value: String(logDetail.value.trace_id || '-') },
    { label: '模块', value: String(logDetail.value.module || '-') },
    {
      label: '模型服务',
      value: logDetail.value.provider
        ? `${formatProviderName(String(logDetail.value.provider))} (${String(logDetail.value.provider)})`
        : '-'
    },
    { label: '模型', value: String(logDetail.value.model_name || '-') },
    { label: '调用类型', value: String(logDetail.value.call_type || '-') },
    { label: '成功', value: logDetail.value.success ? '是' : '否' },
    { label: '延迟', value: logDetail.value.latency_ms == null ? '-' : `${logDetail.value.latency_ms} ms` },
    { label: '令牌数', value: String(logDetail.value.total_tokens || '-') },
    { label: '创建时间', value: formatTime(logDetail.value.created_at as string) }
  ]
})

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    status.value = await getModelGatewayStatusApi()
    const logPage = await getModelCallLogsApi({ page: 1, page_size: 20 })
    logs.value = logPage.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型服务数据读取失败'
  } finally {
    loading.value = false
  }
}

async function testGateway() {
  testing.value = true
  error.value = ''
  testResult.value = null
  try {
    const payload: Record<string, unknown> = { task_type: 'general', prompt: testForm.prompt }
    if (testForm.provider) payload.provider = testForm.provider
    testResult.value = await testModelGatewayApi(payload)
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型网关测试失败'
  } finally {
    testing.value = false
  }
}

async function chatGateway() {
  chatting.value = true
  error.value = ''
  chatResult.value = null
  try {
    const payload: Record<string, unknown> = {
      task_type: 'general',
      prompt: chatForm.prompt,
      trace_source: 'frontend_model_service'
    }
    if (chatForm.provider) payload.provider = chatForm.provider
    chatResult.value = await chatModelGatewayApi(payload)
    await loadAll()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型对话调用失败'
  } finally {
    chatting.value = false
  }
}

async function loadLogDetail(id: string) {
  error.value = ''
  try {
    logDetail.value = await getModelCallLogApi(id)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '模型日志详情读取失败'
  }
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

onMounted(loadAll)
</script>
