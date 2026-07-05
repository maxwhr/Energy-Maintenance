import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { hasRole } from '@/utils/permission'
import { TEXT } from '@/constants/text'
import type { UserRole } from '@/types'

const operatorRoles = ['admin', 'expert', 'engineer'] as UserRole[]
const allRoles = ['admin', 'expert', 'engineer', 'viewer'] as UserRole[]

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { public: true, title: TEXT.login }
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/Register.vue'),
    meta: { public: true, title: '账号申请说明' }
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/error/403.vue'),
    meta: { public: true, title: TEXT.forbidden }
  },
  {
    path: '/',
    component: () => import('@/layout/index.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: TEXT.dashboard, roles: allRoles }
      },
      {
        path: 'device/inventory',
        name: 'DeviceInventory',
        component: () => import('@/views/device/Inventory.vue'),
        meta: { title: TEXT.deviceInventory, roles: operatorRoles }
      },
      {
        path: 'device/models',
        name: 'DeviceModels',
        component: () => import('@/views/device/Models.vue'),
        meta: { title: TEXT.deviceModels, roles: operatorRoles }
      },
      {
        path: 'device/alarms',
        name: 'DeviceAlarms',
        component: () => import('@/views/device/Alarms.vue'),
        meta: { title: TEXT.alarmCodes, roles: operatorRoles }
      },
      {
        path: 'knowledge/documents',
        name: 'KnowledgeDocuments',
        component: () => import('@/views/knowledge/Documents.vue'),
        meta: { title: TEXT.documents, roles: operatorRoles }
      },
      {
        path: 'knowledge/contributions',
        name: 'KnowledgeContributions',
        component: () => import('@/views/knowledge/Contributions.vue'),
        meta: { title: TEXT.contributions, roles: allRoles }
      },
      {
        path: 'knowledge/graph',
        name: 'KnowledgeGraph',
        component: () => import('@/views/knowledgeGraph/index.vue'),
        meta: { title: '知识图谱', roles: allRoles }
      },
      {
        path: 'knowledge/cases',
        name: 'KnowledgeCases',
        component: () => import('@/views/knowledge/Cases.vue'),
        meta: { title: TEXT.cases, roles: operatorRoles }
      },
      {
        path: 'knowledge/search',
        name: 'KnowledgeSearch',
        component: () => import('@/views/knowledge/Search.vue'),
        meta: { title: TEXT.search, roles: operatorRoles }
      },
      {
        path: 'assistant/chat',
        name: 'AssistantChat',
        component: () => import('@/views/assistant/Chat.vue'),
        meta: { title: TEXT.assistantChat, roles: operatorRoles }
      },
      {
        path: 'assistant/history',
        name: 'AssistantHistory',
        component: () => import('@/views/assistant/History.vue'),
        meta: { title: TEXT.assistantHistory, roles: operatorRoles }
      },
      {
        path: 'agents/workbench',
        name: 'AgentWorkbench',
        component: () => import('@/views/agent/Workbench.vue'),
        meta: { title: '智能体工作台', roles: allRoles }
      },
      {
        path: 'diagnosis',
        name: 'Diagnosis',
        component: () => import('@/views/diagnosis/index.vue'),
        meta: { title: TEXT.diagnosis, roles: operatorRoles }
      },
      {
        path: 'sop',
        name: 'SOPCenter',
        component: () => import('@/views/sop/index.vue'),
        meta: { title: TEXT.sopCenter, roles: operatorRoles }
      },
      {
        path: 'workorder/list',
        name: 'WorkorderList',
        component: () => import('@/views/workorder/List.vue'),
        meta: { title: TEXT.workorderList, roles: allRoles }
      },
      {
        path: 'workorder/create',
        name: 'WorkorderCreate',
        component: () => import('@/views/workorder/Create.vue'),
        meta: { title: TEXT.workorderCreate, roles: operatorRoles }
      },
      {
        path: 'workorder/:id',
        name: 'WorkorderDetail',
        component: () => import('@/views/workorder/Detail.vue'),
        meta: { title: TEXT.workorderDetail, hidden: true, roles: allRoles }
      },
      {
        path: 'trace',
        name: 'Trace',
        component: () => import('@/views/trace/index.vue'),
        meta: { title: TEXT.traceCenter, roles: allRoles }
      },
      {
        path: 'review',
        name: 'ReviewCenter',
        component: () => import('@/views/review/index.vue'),
        meta: { title: TEXT.reviewCenter, roles: ['admin', 'expert'] as UserRole[] }
      },
      {
        path: 'model-service',
        name: 'ModelService',
        component: () => import('@/views/model/index.vue'),
        meta: { title: TEXT.modelService, roles: ['admin'] as UserRole[] }
      },
      {
        path: 'media',
        name: 'MediaLibrary',
        component: () => import('@/views/media/index.vue'),
        meta: { title: '媒体资料', roles: operatorRoles }
      },
      {
        path: 'multimodal',
        name: 'MultimodalEvidence',
        component: () => import('@/views/multimodal/index.vue'),
        meta: { title: '多模态证据中心', roles: allRoles }
      },
      {
        path: 'review/corrections',
        name: 'CorrectionCenter',
        component: () => import('@/views/review/Corrections.vue'),
        meta: { title: '人工修正', roles: ['admin', 'expert', 'engineer'] as UserRole[] }
      },
      {
        path: 'system/users',
        name: 'UserManagement',
        component: () => import('@/views/system/Users.vue'),
        meta: { title: '用户管理', roles: ['admin'] as UserRole[] }
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/system/index.vue'),
        meta: { title: TEXT.system, roles: ['admin'] as UserRole[] }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: TEXT.profile, hidden: true }
      }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/dashboard' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore()
  const isPublic = to.meta.public === true

  if (userStore.token && !userStore.user) {
    await userStore.restoreUser()
  }

  if (!userStore.isLoggedIn && !isPublic) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  if (to.path === '/login' && userStore.isLoggedIn) {
    next('/dashboard')
    return
  }

  const required = to.meta.roles as UserRole[] | undefined
  if (required?.length && !hasRole(userStore.roles, required)) {
    next('/403')
    return
  }

  next()
})

export default router
