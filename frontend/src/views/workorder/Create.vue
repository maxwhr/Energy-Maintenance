<template>
  <PageFrame title="新建任务" code="TASK / CREATE" description="创建光伏逆变器检修任务，写入后端 PostgreSQL 维护任务表。">
    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <DataPanel title="任务信息">
      <form class="grid gap-4 lg:grid-cols-2" @submit.prevent="submit">
        <label class="grid gap-1 text-sm font-bold text-slate-200 lg:col-span-2">
          任务标题
          <input v-model.trim="form.title" class="scada-input" required placeholder="例如：SUN2000 绝缘阻抗低告警排查" />
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          关联设备
          <select v-model="form.device_id" class="scada-input">
            <option value="">暂不绑定设备</option>
            <option v-for="device in devices" :key="device.id" :value="device.id">
              {{ device.device_name }} / {{ device.product_series || '-' }}
            </option>
          </select>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          故障类型
          <select v-model="form.fault_type" class="scada-input">
            <option v-for="item in faultTypeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          告警代码
          <input v-model.trim="form.alarm_code" class="scada-input" />
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          优先级
          <select v-model="form.priority" class="scada-input">
            <option v-for="item in priorityOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200">
          负责人
          <select v-model="form.assignee_id" class="scada-input">
            <option value="">暂不指定</option>
            <option v-for="user in users" :key="String(user.id)" :value="String(user.id)">
              {{ String(user.display_name || user.username || user.id) }}
            </option>
          </select>
        </label>
        <label class="grid gap-1 text-sm font-bold text-slate-200 lg:col-span-2">
          故障描述
          <textarea v-model.trim="form.fault_description" class="scada-input min-h-32" placeholder="记录现场现象、告警触发条件和已执行操作。"></textarea>
        </label>
        <div class="flex flex-wrap gap-2 lg:col-span-2">
          <button class="scada-button primary" type="submit" :disabled="saving">
            <Save :size="16" />
            {{ saving ? '创建中' : '创建任务' }}
          </button>
          <RouterLink class="scada-button" to="/workorder/list">返回列表</RouterLink>
        </div>
      </form>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { Save } from '@lucide/vue'
import { createWorkorderApi, getAssignableUsersApi, getDevicesApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { faultTypeOptions, priorityOptions } from '@/types'
import type { AssignableUser, DeviceItem } from '@/types'

const router = useRouter()
const devices = ref<DeviceItem[]>([])
const users = ref<AssignableUser[]>([])
const saving = ref(false)
const error = ref('')
const form = reactive({
  title: '',
  device_id: '',
  fault_type: 'unknown',
  alarm_code: '',
  priority: 'medium',
  assignee_id: '',
  fault_description: ''
})

async function loadOptions() {
  try {
    const devicePage = await getDevicesApi({ page: 1, page_size: 100, device_type: 'pv_inverter' })
    devices.value = devicePage.items
  } catch {
    devices.value = []
  }
  try {
    users.value = await getAssignableUsersApi()
  } catch {
    users.value = []
  }
}

async function submit() {
  saving.value = true
  error.value = ''
  try {
    const payload: Record<string, unknown> = {
      title: form.title,
      fault_type: form.fault_type,
      priority: form.priority,
      alarm_code: form.alarm_code || undefined,
      fault_description: form.fault_description || undefined,
      device_id: form.device_id || undefined,
      assignee_id: form.assignee_id || undefined
    }
    const task = await createWorkorderApi(payload)
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { message: '检修任务已创建' } }))
    await router.push(`/workorder/${task.id}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '任务创建失败'
  } finally {
    saving.value = false
  }
}

onMounted(loadOptions)
</script>
