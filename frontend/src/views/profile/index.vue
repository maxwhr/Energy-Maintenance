<template>
  <PageFrame title="个人中心" code="USER / PROFILE" description="展示当前登录账号信息，角色与权限来自后端认证接口。">
    <DataPanel title="账号信息">
      <div class="grid gap-4 lg:grid-cols-2">
        <Info label="用户名" :value="userStore.username || '-'" />
        <Info label="显示名称" :value="userStore.displayName || '-'" />
        <Info label="角色" :value="roleLabel" />
        <Info label="账号状态" :value="formatStatusLabel(userStore.user?.status)" />
      </div>
    </DataPanel>
  </PageFrame>
</template>

<script setup lang="ts">
import { computed, defineComponent, h } from 'vue'
import DataPanel from '@/components/DataPanel.vue'
import PageFrame from '@/components/PageFrame.vue'
import { TEXT } from '@/constants/text'
import { useUserStore } from '@/stores/user'
import type { UserRole } from '@/types'
import { formatStatusLabel } from '@/utils/display'

const Info = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true }
  },
  setup(props) {
    return () =>
      h('div', { class: 'rounded-md border border-slate-600/20 bg-black/20 p-4' }, [
        h('div', { class: 'text-xs font-bold text-slate-400' }, props.label),
        h('div', { class: 'mt-2 text-lg font-black text-white' }, props.value)
      ])
  }
})

const userStore = useUserStore()
const roleMap: Record<UserRole, string> = {
  admin: TEXT.roleAdmin,
  expert: TEXT.roleExpert,
  engineer: TEXT.roleEngineer,
  viewer: TEXT.roleViewer
}
const roleLabel = computed(() => (userStore.role ? roleMap[userStore.role] : '-'))
</script>
