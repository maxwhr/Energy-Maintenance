<template>
  <PageFrame title="检修任务" code="TASK / LIST" description="读取后端维护任务列表，支持按状态过滤和执行允许的任务流转。">
    <template #actions>
      <RouterLink v-if="canWrite" class="scada-button primary" to="/workorder/create">
        <Plus :size="16" />
        新建任务
      </RouterLink>
      <button class="scada-button" type="button" :disabled="loading" @click="loadTasks">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <DataPanel title="任务列表">
      <div class="mb-4 grid gap-3 md:grid-cols-4">
        <select v-model="filters.task_status" class="scada-input">
          <option value="">不限状态</option>
          <option value="pending">待处理</option>
          <option value="assigned">已分配</option>
          <option value="in_progress">进行中</option>
          <option value="completed">已完成</option>
          <option value="cancelled">已取消</option>
        </select>
        <select v-model="filters.priority" class="scada-input">
          <option value="">不限优先级</option>
          <option v-for="item in priorityOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
        <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索标题或故障描述" />
        <button class="scada-button" type="button" @click="loadTasks">
          <Search :size="16" />
          查询
        </button>
      </div>

      <div v-if="tasks.length" class="space-y-3">
        <article v-for="task in tasks" :key="task.id" class="rounded-md border border-slate-600/20 bg-black/20 p-4">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <RouterLink :to="`/workorder/${task.id}`" class="font-black text-white hover:text-cyan-200">{{ task.title }}</RouterLink>
              <p class="mt-1 text-xs text-slate-400">
                {{ task.device_name || '未绑定设备' }} / {{ labelOf(task.manufacturer) }} / {{ task.product_series || '-' }} / {{ labelOf(task.fault_type) }}
              </p>
              <p class="mt-2 line-clamp-2 text-sm leading-6 text-slate-300">{{ task.fault_description || '未填写故障描述' }}</p>
            </div>
            <div class="flex flex-wrap items-center gap-2 lg:justify-end">
              <StatusPill :value="task.priority" />
              <StatusPill :value="task.task_status || task.status" />
              <button v-if="canStart(task)" class="scada-button !min-h-8 !px-3" type="button" @click="startTask(task.id)">开始</button>
              <button v-if="canComplete(task)" class="scada-button !min-h-8 !px-3" type="button" @click="completeTask(task.id)">完成</button>
              <button v-if="canCancel(task)" class="scada-button !min-h-8 !px-3" type="button" @click="cancelTask(task.id)">取消</button>
            </div>
          </div>
        </article>
      </div>
      <EmptyState v-else text="暂无检修任务" />
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Plus, RefreshCcw, Search } from '@lucide/vue'
import { cancelWorkorderApi, completeWorkorderApi, getWorkordersApi, startWorkorderApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import { faultTypeOptions, manufacturerOptions, priorityOptions } from '@/types'
import type { MaintenanceTask } from '@/types'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const tasks = ref<MaintenanceTask[]>([])
const loading = ref(false)
const error = ref('')
const filters = reactive({ task_status: '', priority: '', keyword: '' })
const canWrite = computed(() => ['admin', 'expert', 'engineer'].includes(userStore.role || ''))

async function loadTasks() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50, device_type: 'pv_inverter' }
    if (filters.task_status) params.status = filters.task_status
    if (filters.priority) params.priority = filters.priority
    if (filters.keyword) params.keyword = filters.keyword
    const result = await getWorkordersApi(params)
    tasks.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '检修任务读取失败'
    tasks.value = []
  } finally {
    loading.value = false
  }
}

async function startTask(id: string) {
  await action(() => startWorkorderApi(id), '任务已开始')
}

async function completeTask(id: string) {
  await action(
    () =>
      completeWorkorderApi(id, {
        root_cause: '现场排查后确认故障原因',
        repair_action: '已按检修规程完成处理',
        verification_result: '复检通过，设备状态已确认',
        maintenance_record_remark: '由前端任务列表快捷完成。'
      }),
    '任务已完成'
  )
}

async function cancelTask(id: string) {
  await action(() => cancelWorkorderApi(id, '前端取消任务'), '任务已取消')
}

async function action(fn: () => Promise<unknown>, message: string) {
  error.value = ''
  try {
    await fn()
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
    await loadTasks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务操作失败'
  }
}

function canStart(task: MaintenanceTask) {
  return canWrite.value && ['pending', 'assigned'].includes(task.task_status || task.status)
}

function canComplete(task: MaintenanceTask) {
  return canWrite.value && (task.task_status || task.status) === 'in_progress'
}

function canCancel(task: MaintenanceTask) {
  return canWrite.value && ['pending', 'assigned', 'in_progress'].includes(task.task_status || task.status)
}

function labelOf(value?: string | null) {
  const options = [...manufacturerOptions, ...faultTypeOptions]
  return options.find((item) => item.value === value)?.label ?? value ?? '-'
}

onMounted(loadTasks)
</script>
