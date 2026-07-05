import type { Component } from 'vue'
import {
  Activity,
  BookOpen,
  Bot,
  Boxes,
  ClipboardCheck,
  ClipboardList,
  Database,
  FileText,
  Gauge,
  GitBranch,
  History,
  Image,
  Images,
  LibraryBig,
  MessageSquare,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Siren,
  Stethoscope,
  UserCog
} from '@lucide/vue'
import type { UserRole } from '@/types'
import { TEXT } from '@/constants/text'

export interface MenuItem {
  path: string
  title: string
  icon: Component
  roles?: UserRole[]
  children?: MenuItem[]
}

const operatorRoles = ['admin', 'expert', 'engineer'] as UserRole[]
const allRoles = ['admin', 'expert', 'engineer', 'viewer'] as UserRole[]

export const menuList: MenuItem[] = [
  {
    path: '/dashboard',
    title: TEXT.dashboard,
    icon: Gauge,
    roles: allRoles
  },
  {
    path: '/device',
    title: '逆变器台账',
    icon: Activity,
    roles: operatorRoles,
    children: [
      { path: '/device/inventory', title: TEXT.deviceInventory, icon: ClipboardList },
      { path: '/device/models', title: TEXT.deviceModels, icon: Boxes },
      { path: '/device/alarms', title: TEXT.alarmCodes, icon: Siren }
    ]
  },
  {
    path: '/knowledge',
    title: '检修知识库',
    icon: LibraryBig,
    roles: allRoles,
    children: [
      { path: '/knowledge/documents', title: TEXT.documents, icon: FileText, roles: operatorRoles },
      { path: '/knowledge/contributions', title: TEXT.contributions, icon: ClipboardCheck, roles: allRoles },
      { path: '/knowledge/graph', title: '知识图谱', icon: GitBranch, roles: allRoles },
      { path: '/knowledge/search', title: TEXT.search, icon: Search, roles: operatorRoles },
      { path: '/knowledge/cases', title: TEXT.cases, icon: BookOpen, roles: operatorRoles },
      { path: '/media', title: '媒体资料', icon: Image, roles: operatorRoles },
      { path: '/multimodal', title: '多模态证据中心', icon: Images, roles: allRoles }
    ]
  },
  {
    path: '/assistant',
    title: '检修问答',
    icon: Bot,
    roles: operatorRoles,
    children: [
      { path: '/assistant/chat', title: TEXT.assistantChat, icon: MessageSquare },
      { path: '/assistant/history', title: TEXT.assistantHistory, icon: History },
      { path: '/agents/workbench', title: '智能体工作台', icon: Bot, roles: allRoles }
    ]
  },
  {
    path: '/diagnosis',
    title: TEXT.diagnosis,
    icon: Stethoscope,
    roles: operatorRoles
  },
  {
    path: '/sop',
    title: TEXT.sopCenter,
    icon: ClipboardCheck,
    roles: operatorRoles
  },
  {
    path: '/workorder',
    title: '检修闭环',
    icon: ClipboardList,
    roles: allRoles,
    children: [
      { path: '/workorder/list', title: TEXT.workorderList, icon: ClipboardList, roles: allRoles },
      { path: '/workorder/create', title: TEXT.workorderCreate, icon: Plus, roles: operatorRoles }
    ]
  },
  {
    path: '/trace',
    title: TEXT.traceCenter,
    icon: GitBranch,
    roles: allRoles
  },
  {
    path: '/review',
    title: TEXT.reviewCenter,
    icon: ShieldCheck,
    roles: ['admin', 'expert', 'engineer'],
    children: [
      { path: '/review', title: TEXT.reviewCenter, icon: ShieldCheck, roles: ['admin', 'expert'] },
      { path: '/review/corrections', title: '人工修正', icon: GitBranch, roles: ['admin', 'expert', 'engineer'] }
    ]
  },
  {
    path: '/model-service',
    title: TEXT.modelService,
    icon: Settings2,
    roles: ['admin']
  },
  {
    path: '/system',
    title: TEXT.system,
    icon: Database,
    roles: ['admin'],
    children: [
      { path: '/system', title: TEXT.system, icon: Database },
      { path: '/system/users', title: '用户管理', icon: UserCog }
    ]
  }
]
