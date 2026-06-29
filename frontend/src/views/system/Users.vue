<template>
  <PageFrame title="用户管理" code="SYSTEM / USERS" description="仅管理员可见，调用后端用户管理接口维护账号、角色和启停状态。">
    <template #actions>
      <button class="scada-button" type="button" :disabled="loading" @click="loadUsers">
        <RefreshCcw :size="16" />
        刷新
      </button>
    </template>

    <div v-if="error" class="rounded-md border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-200">{{ error }}</div>

    <div class="grid gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <DataPanel :title="editingId ? '编辑用户' : '新增用户'">
        <form class="grid gap-3" @submit.prevent="submitUser">
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            用户名
            <input v-model.trim="form.username" class="scada-input" :disabled="!!editingId" required />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            显示名称
            <input v-model.trim="form.display_name" class="scada-input" placeholder="例如：华为逆变器检修专家" />
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            角色
            <select v-model="form.role" class="scada-input">
              <option v-for="item in roleOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            状态
            <select v-model="form.status" class="scada-input">
              <option value="active">启用</option>
              <option value="inactive">停用</option>
            </select>
          </label>
          <label class="grid gap-1 text-sm font-bold text-slate-200">
            密码
            <input v-model.trim="form.password" class="scada-input" type="password" :required="!editingId" placeholder="新增用户至少 8 位；编辑时留空则不修改" />
          </label>
          <div class="flex flex-wrap gap-2">
            <button class="scada-button primary" type="submit" :disabled="saving">
              <Save :size="16" />
              {{ saving ? '保存中' : editingId ? '保存修改' : '创建用户' }}
            </button>
            <button v-if="editingId" class="scada-button" type="button" @click="resetForm">取消编辑</button>
          </div>
        </form>
      </DataPanel>

      <DataPanel title="用户列表" subtitle="支持按角色、状态和用户名过滤。">
        <div class="mb-4 grid gap-3 md:grid-cols-4">
          <input v-model.trim="filters.keyword" class="scada-input" placeholder="搜索用户名或显示名称" />
          <select v-model="filters.role" class="scada-input">
            <option value="">全部角色</option>
            <option v-for="item in roleOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select v-model="filters.status" class="scada-input">
            <option value="">全部状态</option>
            <option value="active">启用</option>
            <option value="inactive">停用</option>
          </select>
          <button class="scada-button" type="button" @click="loadUsers">
            <Search :size="16" />
            查询
          </button>
        </div>

        <div v-if="users.length" class="overflow-x-auto">
          <table class="min-w-full text-left text-sm">
            <thead class="text-xs uppercase text-slate-400">
              <tr>
                <th class="px-3 py-2">账号</th>
                <th class="px-3 py-2">角色</th>
                <th class="px-3 py-2">状态</th>
                <th class="px-3 py-2">创建时间</th>
                <th class="px-3 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in users" :key="user.id" class="border-t border-slate-600/20 text-slate-200">
                <td class="px-3 py-3">
                  <div class="font-bold text-white">{{ user.username }}</div>
                  <div class="text-xs text-slate-400">{{ formatUserDisplayName(user.display_name, user.username) }}</div>
                </td>
                <td class="px-3 py-3">{{ roleLabel(user.role) }}</td>
                <td class="px-3 py-3"><StatusPill :value="user.is_active === false ? 'inactive' : user.status" /></td>
                <td class="px-3 py-3">{{ formatTime(user.created_at) }}</td>
                <td class="px-3 py-3">
                  <div class="flex flex-wrap gap-2">
                    <button class="scada-button !min-h-8 !px-3" type="button" @click="editUser(user)">编辑</button>
                    <button v-if="user.is_active !== false && user.status !== 'inactive'" class="scada-button !min-h-8 !px-3" type="button" @click="disableUser(user.id)">禁用</button>
                    <button v-else class="scada-button !min-h-8 !px-3" type="button" @click="enableUser(user.id)">启用</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <EmptyState v-else text="暂无用户数据" />
      </DataPanel>
    </div>
  </PageFrame>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { RefreshCcw, Save, Search } from '@lucide/vue'
import { createUserApi, disableUserApi, enableUserApi, getUsersApi, updateUserApi } from '@/api'
import DataPanel from '@/components/DataPanel.vue'
import EmptyState from '@/components/EmptyState.vue'
import PageFrame from '@/components/PageFrame.vue'
import StatusPill from '@/components/StatusPill.vue'
import type { BackendUser, UserRole } from '@/types'
import { formatUserDisplayName } from '@/utils/display'

const roleOptions: Array<{ label: string; value: UserRole }> = [
  { label: '管理员', value: 'admin' },
  { label: '专家', value: 'expert' },
  { label: '工程师', value: 'engineer' },
  { label: '只读用户', value: 'viewer' }
]

const users = ref<BackendUser[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const editingId = ref('')
const filters = reactive({ keyword: '', role: '', status: '' })
const form = reactive({
  username: '',
  display_name: '',
  role: 'viewer' as UserRole,
  status: 'active',
  password: ''
})

async function loadUsers() {
  loading.value = true
  error.value = ''
  try {
    const params: Record<string, string | number> = { page: 1, page_size: 50 }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.role) params.role = filters.role
    if (filters.status) params.status = filters.status
    const result = await getUsersApi(params)
    users.value = result.items
  } catch (err) {
    error.value = err instanceof Error ? err.message : '用户列表读取失败'
    users.value = []
  } finally {
    loading.value = false
  }
}

async function submitUser() {
  saving.value = true
  error.value = ''
  try {
    const payload: Record<string, unknown> = {
      display_name: form.display_name || undefined,
      role: form.role,
      status: form.status
    }
    if (form.password) payload.password = form.password
    if (editingId.value) {
      await updateUserApi(editingId.value, payload)
      toast('用户已更新')
    } else {
      await createUserApi({
        ...payload,
        username: form.username,
        password: form.password
      })
      toast('用户已创建')
    }
    resetForm()
    await loadUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '用户保存失败'
  } finally {
    saving.value = false
  }
}

function editUser(user: BackendUser) {
  editingId.value = user.id
  form.username = user.username
  form.display_name = user.display_name ?? ''
  form.role = user.role as UserRole
  form.status = user.status || (user.is_active === false ? 'inactive' : 'active')
  form.password = ''
}

async function disableUser(id: string) {
  if (!window.confirm('确认禁用该用户？')) return
  await runAction(() => disableUserApi(id), '用户已禁用')
}

async function enableUser(id: string) {
  await runAction(() => enableUserApi(id), '用户已启用')
}

async function runAction(fn: () => Promise<unknown>, message: string) {
  error.value = ''
  try {
    await fn()
    toast(message)
    await loadUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '用户操作失败'
  }
}

function resetForm() {
  editingId.value = ''
  form.username = ''
  form.display_name = ''
  form.role = 'viewer'
  form.status = 'active'
  form.password = ''
}

function roleLabel(value?: string) {
  return roleOptions.find((item) => item.value === value)?.label ?? value ?? '-'
}

function formatTime(value?: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN') : '-'
}

function toast(message: string) {
  window.dispatchEvent(new CustomEvent('app:toast', { detail: { message } }))
}

onMounted(loadUsers)
</script>
