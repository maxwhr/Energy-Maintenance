<template>
  <div class="flex h-screen overflow-hidden bg-[#f6f9fc] text-[#172538]">
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-72 flex-col border-r border-[#dbe7f3] bg-white transition-transform duration-200 lg:static lg:translate-x-0"
      :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full'"
    >
      <div class="flex h-16 w-full items-center gap-3 border-b border-[#dbe7f3] px-2 sm:px-2.5">
        <div class="grid h-10 w-10 -translate-x-1 place-items-center rounded-md bg-[#195FA8] font-black text-white">EM</div>
        <div class="min-w-0 -translate-x-1">
          <div class="truncate text-sm font-black text-[#172538]">Energy-Maintenance</div>
          <div class="truncate text-[11px] text-[#4f6f8f]">光伏逆变器检修工作台</div>
        </div>
      </div>

      <div class="m-3 rounded-md border border-[#cfe2f3] bg-[#eef6ff] p-3">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2 text-sm font-bold text-[#172538]">
            <span class="status-dot text-emerald-300"></span>
            光伏逆变器检修区
          </div>
          <span class="text-xs font-bold text-[#195FA8]">接口</span>
        </div>
        <div class="mt-2 grid grid-cols-2 gap-2 font-mono text-[11px] text-[#53697f]">
          <span>华为 SUN2000</span>
          <span>FusionSolar</span>
          <span>阳光电源 SG</span>
          <span>来源追溯</span>
        </div>
      </div>

      <nav class="flex-1 overflow-y-auto px-2 pb-4">
        <template v-for="item in visibleMenus" :key="item.path">
          <button
            type="button"
            class="mt-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-bold transition"
            :class="isActiveGroup(item) ? 'bg-[#195FA8] text-white' : 'text-[#53697f] hover:bg-[#eef6ff] hover:text-[#195FA8]'"
            @click="go(item)"
          >
            <component :is="item.icon" :size="18" />
            <span class="flex-1">{{ item.title }}</span>
            <ChevronDown v-if="item.children?.length" :size="15" :class="openGroups.has(item.path) ? 'rotate-180' : ''" />
          </button>
          <div v-if="item.children?.length && openGroups.has(item.path)" class="ml-6 border-l border-[#dbe7f3] pl-2">
            <RouterLink
              v-for="child in item.children"
              :key="child.path"
              :to="child.path"
              class="mt-1 flex items-center gap-2 rounded-md px-3 py-2 text-sm transition"
              :class="activeMenu === child.path ? 'bg-[#195FA8] text-white' : 'text-[#53697f] hover:bg-[#eef6ff] hover:text-[#195FA8]'"
              @click="sidebarOpen = false"
            >
              <component :is="child.icon" :size="16" />
              {{ child.title }}
            </RouterLink>
          </div>
        </template>
      </nav>

      <div class="border-t border-[#dbe7f3] p-3">
        <button class="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-[#53697f] hover:bg-[#eef6ff] hover:text-[#195FA8]" type="button" @click="logout">
          <LogOut :size="17" />
          {{ TEXT.logout }}
        </button>
      </div>
    </aside>

    <button
      v-if="sidebarOpen"
      class="fixed inset-0 z-30 bg-slate-900/30 lg:hidden"
      type="button"
      aria-label="关闭导航"
      @click="sidebarOpen = false"
    ></button>

    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-16 shrink-0 items-center justify-between border-b border-[#dbe7f3] bg-white px-4">
        <div class="flex min-w-0 items-center gap-3">
          <button class="scada-button !min-h-9 !px-2 lg:hidden" type="button" @click="sidebarOpen = true">
            <Menu :size="18" />
          </button>
          <div class="min-w-0">
            <div class="truncate text-sm font-black text-[#172538]">{{ currentTitle }}</div>
            <div class="hidden items-center gap-3 font-mono text-[11px] text-[#64788f] sm:flex">
              <span>光伏逆变器 / {{ route.path }}</span>
              <span>后端接口</span>
              <span>{{ currentTime }}</span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <div class="hidden items-center gap-2 rounded-md border border-[#dbe7f3] bg-[#f8fbfe] px-3 py-2 md:flex">
            <span class="status-dot text-emerald-300"></span>
            <span class="text-xs font-bold text-[#33485f]">后端接口通道</span>
          </div>
          <RouterLink to="/profile" class="flex items-center gap-2 rounded-md px-2 py-2 hover:bg-slate-100">
            <div class="grid h-8 w-8 place-items-center rounded-md bg-[#195FA8] text-xs font-black text-white">
              {{ initials }}
            </div>
            <div class="hidden text-left md:block">
              <div class="text-xs font-bold text-[#172538]">{{ displayName }}</div>
              <div class="text-[11px] text-[#64788f]">{{ roleLabel }}</div>
            </div>
          </RouterLink>
        </div>
      </header>

      <main class="min-h-0 flex-1 overflow-y-auto bg-[#f6f9fc] p-4 lg:p-5">
        <RouterView v-slot="{ Component }">
          <Transition name="page" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
    <AppToast />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { ChevronDown, LogOut, Menu } from '@lucide/vue'
import AppToast from '@/components/AppToast.vue'
import { menuList, type MenuItem } from '@/router/menus'
import { useUserStore } from '@/stores/user'
import { hasRole } from '@/utils/permission'
import { TEXT } from '@/constants/text'
import { formatRoleLabel, formatUserDisplayName } from '@/utils/display'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const sidebarOpen = ref(false)
const openGroups = ref(new Set<string>(['/device', '/assistant', '/knowledge', '/workorder', '/review', '/system']))
const currentTime = ref('')
let timer = 0

const activeMenu = computed(() => {
  if (route.path.startsWith('/workorder/') && route.params.id) return '/workorder/list'
  return route.path
})

const currentTitle = computed(() => (route.meta.title as string) || TEXT.dashboard)
const roleLabel = computed(() => formatRoleLabel(userStore.roles[0]))
const displayName = computed(() => formatUserDisplayName(userStore.displayName, userStore.username))
const initials = computed(() => (userStore.displayName || userStore.username || 'EM').slice(0, 2).toUpperCase())

const visibleMenus = computed(() => filterMenus(menuList))

function filterMenus(items: MenuItem[]): MenuItem[] {
  return items
    .filter((item) => hasRole(userStore.roles, item.roles))
    .map((item) => ({
      ...item,
      children: item.children ? filterMenus(item.children) : undefined
    }))
}

function isActiveGroup(item: MenuItem) {
  return route.path === item.path || route.path.startsWith(`${item.path}/`)
}

function go(item: MenuItem) {
  if (item.children?.length) {
    const next = new Set(openGroups.value)
    next.has(item.path) ? next.delete(item.path) : next.add(item.path)
    openGroups.value = next
    return
  }
  sidebarOpen.value = false
  router.push(item.path)
}

async function logout() {
  await userStore.logout()
  router.push('/login')
}

function tick() {
  currentTime.value = new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date())
}

onMounted(() => {
  tick()
  timer = window.setInterval(tick, 1000)
})

onBeforeUnmount(() => window.clearInterval(timer))
</script>
