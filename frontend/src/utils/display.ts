const metricSectionLabels: Record<string, string> = {
  devices: '设备台账',
  knowledge: '知识库',
  qa: '问答记录',
  diagnosis: '诊断记录',
  tasks: '检修任务',
  sop: 'SOP 作业',
  maintenance: '维修履历',
  media: '媒体附件',
  users: '用户',
  model: '模型服务',
  review: '审核记录',
  corrections: '人工修正',
  knowledge_contributions: '一线经验'
}

const metricLabels: Record<string, string> = {
  total: '总数',
  items: '附件数',
  normal: '正常',
  fault: '故障',
  maintenance: '检修中',
  offline: '离线',
  retired: '已退役',
  documents: '文档数',
  chunks: '切片数',
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  archived: '已归档',
  records: '记录数',
  pending: '待处理',
  assigned: '已分派',
  in_progress: '进行中',
  completed: '已完成',
  cancelled: '已取消',
  canceled: '已取消',
  templates: '模板数',
  executions: '执行记录',
  accepted: '已采纳'
}

const providerLabels: Record<string, string> = {
  rule_based: '规则兜底模型',
  local_llama_cpp: '本地 llama.cpp 模型',
  cloud_openai: '云端 OpenAI 兼容模型'
}

const statusLabels: Record<string, string> = {
  pending: '待处理',
  assigned: '已分派',
  not_started: '未开始',
  processing: '处理中',
  processed: '已识别',
  in_progress: '进行中',
  completed: '已完成',
  aborted: '已中止',
  canceled: '已取消',
  cancelled: '已取消',
  running: '运行中',
  normal: '正常',
  fault: '故障',
  maintenance: '检修中',
  offline: '离线',
  online: '在线',
  connected: '已连接',
  disconnected: '未连接',
  available: '可用',
  unavailable: '不可用',
  enabled: '已启用',
  disabled: '未启用',
  not_configured: '未配置',
  not_checked: '未检查',
  ready: '就绪',
  parsed: '已解析',
  parsing: '解析中',
  embedded: '已向量化',
  uploaded: '已上传',
  success: '成功',
  failed: '失败',
  active: '启用',
  inactive: '停用',
  retired: '已退役',
  draft: '草稿',
  submitted: '已提交',
  changes_requested: '需修改',
  pending_review: '待审核',
  approved: '已通过',
  rejected: '已驳回',
  converted: '已入库',
  archived: '已归档',
  accepted: '已采纳',
  warning: '预警',
  error: '故障',
  info: '提示',
  high: '高优先级',
  critical: '紧急',
  urgent: '紧急',
  medium: '中优先级',
  low: '低优先级'
}

const roleLabels: Record<string, string> = {
  admin: '管理员',
  expert: '专家',
  engineer: '工程师',
  viewer: '只读用户'
}

const mediaTypeLabels: Record<string, string> = {
  fault_image: '故障图片',
  nameplate: '铭牌图片',
  site_photo: '现场图片',
  inspection_photo: '巡检/完工图片',
  other: '其他图片'
}

const recordTypeLabels: Record<string, string> = {
  qa: '问答记录',
  diagnosis: '诊断记录',
  task: '检修任务',
  maintenance_record: '检修记录',
  sop: 'SOP 作业',
  sop_execution: 'SOP 执行',
  knowledge_document: '知识文档',
  knowledge_contribution: '一线经验',
  media: '媒体资料',
  knowledge_graph_node: '知识图谱节点',
  knowledge_graph_edge: '知识图谱关系',
  knowledge_graph_extraction_run: '图谱抽取运行'
}

const contributionTypeLabels: Record<string, string> = {
  maintenance_experience: '一线检修经验',
  experience_summary: '一线检修经验',
  fault_case: '故障案例补充',
  alarm_experience: '告警处理经验',
  sop_suggestion: '规程优化建议',
  procedure: '规程优化建议'
}

const faultTypeLabels: Record<string, string> = {
  low_insulation_resistance: '低绝缘阻抗',
  dc_abnormal: '直流侧异常',
  ac_overvoltage: '交流过压',
  ac_undervoltage: '交流欠压',
  grid_connection_fault: '并网故障',
  over_temperature: '过温',
  fan_fault: '风扇故障',
  communication_interruption: '通信中断',
  device_offline: '设备离线',
  mppt_abnormal: 'MPPT 异常',
  low_power_generation: '发电量低',
  alarm_code_query: '告警代码查询',
  unknown: '未知'
}

const deviceTypeLabels: Record<string, string> = {
  pv_inverter: '光伏逆变器',
  inverter: '光伏逆变器'
}

const pageCodeLabels: Record<string, string> = {
  'SCREEN / DASHBOARD': '运行总览',
  'DEVICE / INVENTORY': '设备台账',
  'DEVICE / FAULT TYPES': '告警类型',
  'DEVICE / SERIES': '产品系列',
  'KNOWLEDGE / DOCUMENTS': '知识文档',
  'KNOWLEDGE / CONTRIBUTIONS': '一线经验',
  'KNOWLEDGE / GRAPH': '知识图谱',
  'KNOWLEDGE / SEARCH': '知识检索',
  'KNOWLEDGE / CASES': '故障案例',
  'MEDIA / LIBRARY': '媒体资料',
  'RETRIEVAL / QA': '检修问答',
  'RETRIEVAL / RECORDS': '问答记录',
  'DIAGNOSIS / ANALYZE': '故障诊断',
  'SOP / WORKFLOW': '作业规程',
  'TASK / LIST': '检修任务',
  'TASK / CREATE': '新建任务',
  'TASK / DETAIL': '任务详情',
  'RECORD / TRACE': '记录追溯',
  'REVIEW / KNOWLEDGE': '知识审核',
  'CORRECTIONS / REVIEW': '人工修正',
  'MODEL / GATEWAY': '模型服务',
  'SYSTEM / STATUS': '系统状态',
  'SYSTEM / USERS': '用户管理',
  'USER / PROFILE': '个人中心',
  'REPORT / OVERVIEW': '统计报表'
}

export function formatMetricSectionLabel(value: string) {
  return metricSectionLabels[value] ?? value
}

export function formatMetricLabel(value: string) {
  return metricLabels[value] ?? statusLabels[value] ?? value
}

export function formatProviderName(value?: string | null) {
  if (!value) return '未指定模型服务'
  return providerLabels[value] ?? value
}

export const formatProviderLabel = formatProviderName

export function formatProviderMessage(provider?: string | null, status?: string | null, fallback?: string | null) {
  if (provider === 'rule_based') return '规则兜底模型无需外部模型服务，可直接使用。'
  if (provider === 'local_llama_cpp' && status === 'disabled') return '本地 llama.cpp 模型当前未启用。'
  if (provider === 'cloud_openai' && status === 'disabled') return '云端 OpenAI 兼容模型当前未启用。'
  return fallback || '暂无状态说明'
}

export function formatStatusLabel(value?: string | null) {
  if (!value) return '-'
  return statusLabels[value] ?? value
}

export function formatRoleLabel(value?: string | null) {
  if (!value) return '未授权'
  return roleLabels[value] ?? value
}

export function formatMediaTypeLabel(value?: string | null) {
  if (!value) return '-'
  return mediaTypeLabels[value] ?? value
}

export function formatRecordTypeLabel(value?: string | null) {
  if (!value) return '-'
  return recordTypeLabels[value] ?? value
}

export function formatContributionTypeLabel(value?: string | null) {
  if (!value) return '-'
  return contributionTypeLabels[value] ?? value
}

export function formatFaultTypeLabel(value?: string | null) {
  if (!value) return '-'
  return faultTypeLabels[value] ?? value
}

export function formatDeviceTypeLabel(value?: string | null) {
  if (!value) return '-'
  return deviceTypeLabels[value] ?? value
}

export function formatTaskStatusLabel(value?: string | null) {
  return formatStatusLabel(value)
}

export function formatReviewStatusLabel(value?: string | null) {
  return formatStatusLabel(value)
}

export function formatPageCode(value?: string | null) {
  if (!value) return ''
  return pageCodeLabels[value] ?? value
}

export function formatUserDisplayName(displayName?: string | null, username?: string | null) {
  if (displayName === 'System Administrator') return '系统管理员'
  return displayName || username || '未登录'
}

const knowledgeGraphNodeTypeLabels: Record<string, string> = {
  manufacturer: '厂家',
  product_series: '产品系列',
  device_model: '设备型号',
  device: '设备',
  fault: '故障',
  alarm: '告警',
  component: '部件',
  symptom: '故障现象',
  cause: '可能原因',
  inspection_item: '排查项',
  action: '处理措施',
  tool: '工具',
  part: '备件',
  safety_risk: '安全风险',
  sop_template: 'SOP 模板',
  sop_step: 'SOP 步骤',
  knowledge_document: '知识文档',
  knowledge_chunk: '知识切片',
  maintenance_task: '检修任务',
  maintenance_record: '维修履历',
  media_evidence: '媒体证据',
  contribution: '一线经验'
}

const knowledgeGraphRelationLabels: Record<string, string> = {
  BELONGS_TO: '属于',
  HAS_MODEL: '包含型号',
  HAS_DEVICE: '关联设备',
  HAS_FAULT: '关联故障',
  HAS_ALARM: '关联告警',
  HAS_SYMPTOM: '表现为',
  CAUSED_BY: '可能原因',
  CHECK_BY: '排查方式',
  RESOLVED_BY: '处理措施',
  USES_TOOL: '使用工具',
  REQUIRES_PART: '需要备件',
  HAS_SAFETY_RISK: '安全风险',
  GUIDED_BY_SOP: '作业规程',
  HAS_STEP: '包含步骤',
  EVIDENCED_BY: '证据支持',
  MENTIONED_IN: '提及于',
  DERIVED_FROM: '来源于',
  RECURRENT_WITH: '复现关联',
  RELATED_TO: '相关'
}

export function formatKnowledgeGraphNodeType(value?: string | null) {
  if (!value) return '-'
  return knowledgeGraphNodeTypeLabels[value] ?? value
}

export function formatKnowledgeGraphRelation(value?: string | null) {
  if (!value) return '-'
  return knowledgeGraphRelationLabels[value] ?? value
}
