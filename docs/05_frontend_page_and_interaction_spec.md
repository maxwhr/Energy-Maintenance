# 05 前端页面与交互规格文档

**Document Name:** `05_frontend_page_and_interaction_spec.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Frontend Stack:** Vue 3 + Vite + TypeScript + Vue Router + Pinia + Axios + Element Plus  
**API Prefix:** `/api`  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版前端页面、交互流程、表单字段、接口调用、状态展示和验收标准。

本项目第一版已经明确收敛为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

因此，前端页面不应再做成泛新能源设备平台、通用知识库系统或普通聊天软件，而应围绕：

```text
华为 Huawei / SUN2000 / FusionSolar
阳光电源 Sungrow / SG 系列
光伏逆变器 PV Inverter
告警排查
故障诊断
检修任务
记录追溯
国产化部署适配
```

前端页面必须服务于真实业务闭环：

```text
进入系统首页
    ↓
上传华为 / 阳光逆变器资料
    ↓
查看文档解析与知识切片
    ↓
输入检修问题
    ↓
查看检索回答和真实来源
    ↓
进行故障辅助诊断
    ↓
创建检修任务
    ↓
查看问答、诊断和任务记录
    ↓
检查系统运行状态
```

---

## 2. 前端总体设计原则

### 2.1 页面风格定位

前端风格应体现：

```text
工业运维
设备检修
知识检索
作业辅助
国产化系统
专业、克制、清晰
```

建议视觉风格：

```text
主色：深蓝 / 科技蓝
辅助色：工业绿 / 告警橙 / 危险红
背景：灰白 / 深浅分区
组件：卡片、表格、状态标签、步骤条、抽屉、折叠面板
```

禁止做成：

```text
普通聊天机器人
教育平台
电商管理后台
花哨大屏
泛新能源展示页
车辆维修系统
```

---

### 2.2 第一版业务范围必须在页面中体现

页面文案、筛选项、示例问题、默认数据都必须围绕：

```text
华为 / 阳光电源
光伏逆变器
SUN2000 / FusionSolar / SG
告警排查
绝缘阻抗低
过温降额
通信中断
并网异常
MPPT 异常
功率偏低
```

前端不应主动暴露以下设备类型作为第一版主选项：

```text
储能电池系统
箱式变压器
电力巡检设备
泛新能源设备
通用能源设备
汽车 / 摩托车 / 发动机
```

---

### 2.3 所有数据优先来自后端接口

除非是页面占位说明，否则前端不得假造业务成功结果。

禁止：

```text
1. 接口失败但页面显示“上传成功”
2. 问答失败但前端展示固定模拟回答
3. references 为空但前端编造来源
4. 数据库不可用但页面显示系统正常
```

允许：

```text
1. 空状态展示引导文案
2. 本地静态枚举选项
3. 首页展示固定系统定位说明
```

---

### 2.4 前端接口路径统一使用 `/api`

前端 Axios 基础路径应统一为：

```text
/api
```

开发环境通过 Vite proxy 转发到后端：

```text
http://127.0.0.1:8000
```

禁止在多个页面中分散写死后端地址。

---

## 3. 前端技术结构

推荐目录结构：

```text
frontend/
├── src/
│   ├── api/
│   │   ├── request.ts
│   │   ├── system.ts
│   │   ├── knowledge.ts
│   │   ├── retrieval.ts
│   │   ├── maintenance.ts
│   │   ├── records.ts
│   │   └── devices.ts
│   ├── assets/
│   │   └── styles.css
│   ├── components/
│   │   ├── StatusTag.vue
│   │   ├── ManufacturerSelect.vue
│   │   ├── ProductSeriesSelect.vue
│   │   ├── DocumentTypeSelect.vue
│   │   ├── FaultTypeSelect.vue
│   │   ├── ReferenceList.vue
│   │   └── EmptyState.vue
│   ├── layouts/
│   │   └── MainLayout.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   └── app.ts
│   ├── types/
│   │   ├── common.ts
│   │   ├── knowledge.ts
│   │   ├── retrieval.ts
│   │   ├── maintenance.ts
│   │   └── records.ts
│   ├── views/
│   │   ├── DashboardView.vue
│   │   ├── KnowledgeBaseView.vue
│   │   ├── RetrievalChatView.vue
│   │   ├── FaultDiagnosisView.vue
│   │   ├── MaintenanceTaskView.vue
│   │   ├── RecordCenterView.vue
│   │   ├── SystemStatusView.vue
│   │   └── LoginView.vue
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
└── tsconfig.json
```

如当前项目尚未创建 `RecordCenterView.vue`、`records.ts` 或 `types/` 目录，应作为后续小任务补充。

---

## 4. 通用枚举选项

前端枚举必须与后端、数据库和 API 文档一致。

---

### 4.1 厂家 manufacturer

```ts
export const MANUFACTURER_OPTIONS = [
  { label: "华为", value: "huawei" },
  { label: "阳光电源", value: "sungrow" }
]
```

显示建议：

| 值 | 页面显示 |
|---|---|
| huawei | 华为 |
| sungrow | 阳光电源 |

---

### 4.2 产品系列 product_series

```ts
export const PRODUCT_SERIES_OPTIONS = [
  { label: "SUN2000", value: "SUN2000", manufacturer: "huawei" },
  { label: "FusionSolar", value: "FusionSolar", manufacturer: "huawei" },
  { label: "SG 系列", value: "SG", manufacturer: "sungrow" }
]
```

说明：

- 选择厂家后，应联动过滤产品系列；
- 未选择厂家时，可显示全部；
- 第一版不应展示其他品牌系列。

---

### 4.3 设备类型 device_type

第一版仅展示：

```ts
export const DEVICE_TYPE_OPTIONS = [
  { label: "光伏逆变器", value: "pv_inverter" }
]
```

`other` 仅用于兼容历史数据，不作为页面主选项。

---

### 4.4 文档类型 document_type

```ts
export const DOCUMENT_TYPE_OPTIONS = [
  { label: "设备手册", value: "manual" },
  { label: "告警代码", value: "alarm_code" },
  { label: "检修规程", value: "sop" },
  { label: "故障案例", value: "fault_case" },
  { label: "巡检规范", value: "inspection_standard" },
  { label: "检修记录", value: "maintenance_record" }
]
```

---

### 4.5 故障类型 fault_type

```ts
export const FAULT_TYPE_OPTIONS = [
  { label: "绝缘阻抗低", value: "low_insulation_resistance" },
  { label: "直流侧异常", value: "dc_abnormal" },
  { label: "交流过压", value: "ac_overvoltage" },
  { label: "交流欠压", value: "ac_undervoltage" },
  { label: "并网异常", value: "grid_connection_fault" },
  { label: "逆变器过温", value: "over_temperature" },
  { label: "风扇异常", value: "fan_fault" },
  { label: "通信中断", value: "communication_interruption" },
  { label: "设备离线", value: "device_offline" },
  { label: "MPPT 异常", value: "mppt_abnormal" },
  { label: "功率偏低", value: "low_power_generation" },
  { label: "告警代码查询", value: "alarm_code_query" }
]
```

---

### 4.6 任务优先级 priority

```ts
export const PRIORITY_OPTIONS = [
  { label: "低", value: "low", type: "info" },
  { label: "中", value: "medium", type: "warning" },
  { label: "高", value: "high", type: "danger" },
  { label: "严重", value: "critical", type: "danger" }
]
```

---

### 4.7 任务状态 task_status

```ts
export const TASK_STATUS_OPTIONS = [
  { label: "待处理", value: "pending" },
  { label: "处理中", value: "in_progress" },
  { label: "已完成", value: "completed" },
  { label: "已取消", value: "cancelled" }
]
```

---

### 4.8 解析状态 parse_status

```ts
export const PARSE_STATUS_OPTIONS = [
  { label: "待解析", value: "pending" },
  { label: "解析中", value: "processing" },
  { label: "已解析", value: "parsed" },
  { label: "解析失败", value: "failed" }
]
```

状态颜色建议：

| 状态 | 标签类型 |
|---|---|
| pending | info |
| processing | warning |
| parsed | success |
| failed | danger |

---

## 5. 全局布局 MainLayout

### 5.1 布局结构

页面采用典型后台管理布局：

```text
┌──────────────────────────────────────────────┐
│ Top Header: Energy-Maintenance / 状态 / 用户 │
├───────────────┬──────────────────────────────┤
│ Sidebar       │ Main Content                 │
│ - 首页        │                              │
│ - 知识库      │                              │
│ - 检修问答    │                              │
│ - 故障诊断    │                              │
│ - 检修任务    │                              │
│ - 记录追溯    │                              │
│ - 系统状态    │                              │
└───────────────┴──────────────────────────────┘
```

---

### 5.2 侧边栏菜单

菜单项固定为：

| 菜单 | 路由 | 页面 |
|---|---|---|
| 系统首页 | `/dashboard` | DashboardView |
| 知识库管理 | `/knowledge` | KnowledgeBaseView |
| 检修问答 | `/retrieval` | RetrievalChatView |
| 故障诊断 | `/diagnosis` | FaultDiagnosisView |
| 检修任务 | `/tasks` | MaintenanceTaskView |
| 记录追溯 | `/records` | RecordCenterView |
| 系统状态 | `/status` | SystemStatusView |

如果当前项目仍有 `/login`，登录页可保留，但第一版不强制做真实鉴权。

---

### 5.3 顶部栏内容

顶部栏建议展示：

```text
系统名称：Energy-Maintenance
副标题：国产光伏逆变器检修知识检索与作业辅助系统
当前运行环境：development / production
数据库状态：connected / disconnected
```

如果数据库状态接口暂未实现，可先在 SystemStatus 页面展示，不必顶部实时刷新。

---

### 5.4 响应式要求

第一版优先桌面端展示：

```text
1366px 及以上宽度体验良好
```

不强制做手机端适配，但页面不能在普通笔记本屏幕上严重错位。

---

## 6. DashboardView 系统首页

---

### 6.1 页面目标

系统首页用于让用户快速理解系统定位和当前运行状态。

必须突出：

```text
华为 / 阳光电源
光伏逆变器
检修知识库
可追溯问答
故障辅助诊断
检修任务管理
```

---

### 6.2 页面结构

建议分为四块：

```text
1. 顶部项目说明区
2. 核心统计卡片区
3. 典型故障入口区
4. 功能模块入口区
```

---

### 6.3 顶部项目说明区

显示文案建议：

```text
Energy-Maintenance
面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统

系统聚焦 SUN2000 / FusionSolar 与 Sungrow SG 系列逆变器，
围绕告警代码解释、绝缘阻抗低、过温降额、通信中断、MPPT 异常和功率偏低等典型场景，
提供知识库管理、检修问答、故障诊断、任务管理和记录追溯能力。
```

禁止出现：

```text
泛新能源设备
储能电池系统
箱式变压器
车辆维修
教育系统
```

---

### 6.4 统计卡片

调用接口：

```http
GET /api/system/status
```

展示卡片：

| 卡片 | 字段 | 说明 |
|---|---|---|
| 知识库文档 | document_count | 文档总数 |
| 知识切片 | chunk_count | chunks 总数 |
| 问答记录 | qa_record_count | 检修问答记录数 |
| 诊断记录 | diagnosis_record_count | 故障诊断记录数 |
| 检修任务 | maintenance_task_count | 任务数 |
| 数据库状态 | database_status | connected / disconnected |

---

### 6.5 典型故障入口

展示按钮或卡片：

```text
绝缘阻抗低
逆变器过温
通信中断
并网异常
MPPT 异常
功率偏低
告警代码查询
```

点击后可跳转到：

```text
FaultDiagnosisView 或 RetrievalChatView
```

并预填 `fault_type` 或问题模板。

---

### 6.6 空状态

如果 `/api/system/status` 失败：

```text
系统状态加载失败，请检查后端服务和数据库连接。
```

不得显示假的统计数据。

---

### 6.7 验收标准

```text
1. 页面文案聚焦华为/阳光光伏逆变器
2. 能调用 /api/system/status
3. 数据库不可用时显示异常提示
4. 统计数据来自后端
5. 入口能跳转到对应功能页面
```

---

## 7. KnowledgeBaseView 知识库管理页

---

### 7.1 页面目标

知识库页面用于上传和管理华为、阳光电源光伏逆变器资料。

核心能力：

```text
上传资料
解析文本
生成切片
查看文档
查看切片
筛选厂家/系列/文档类型/解析状态
```

---

### 7.2 页面结构

建议结构：

```text
1. 页面标题与说明
2. 文档上传卡片
3. 文档筛选区
4. 文档列表表格
5. 文档切片抽屉 / 详情区
```

---

### 7.3 页面标题文案

建议：

```text
知识库管理
管理华为 SUN2000 / FusionSolar 与阳光电源 SG 系列光伏逆变器资料，
支持手册、告警代码、检修规程、故障案例和巡检规范上传解析。
```

---

### 7.4 上传表单字段

调用接口：

```http
POST /api/knowledge/documents/upload
```

表单字段：

| 字段 | 组件 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| file | Upload | 是 | 无 | 支持 txt/md/pdf/docx |
| title | Input | 否 | 文件名 | 文档标题 |
| manufacturer | Select | 是 | huawei | 华为/阳光电源 |
| product_series | Select | 否 | 根据厂家 | SUN2000/FusionSolar/SG |
| model | Input | 否 | 空 | 具体型号 |
| device_type | Select | 是 | pv_inverter | 光伏逆变器 |
| document_type | Select | 是 | manual | 文档类型 |
| source | Input | 否 | user_upload | 来源 |
| summary | Textarea | 否 | 空 | 摘要 |

---

### 7.5 上传限制提示

页面必须提示：

```text
支持 txt、md、pdf、docx 文件；
文本型 PDF 可解析，扫描版 PDF 暂不支持 OCR；
单文件最大 50MB；
资料应优先为华为或阳光电源光伏逆变器相关手册、告警代码或检修规程。
```

---

### 7.6 上传成功状态

上传成功后：

```text
1. 显示“上传并解析成功”
2. 显示 parse_status
3. 显示 chunk_count
4. 自动刷新文档列表
5. 清空或保留表单由前端决定，但不能重复提交
```

成功提示示例：

```text
文档已解析完成，共生成 12 个知识切片。
```

---

### 7.7 上传失败状态

失败时必须显示后端返回的 message。

常见失败：

```text
文件为空
文件类型不支持
文件超过大小限制
PDF 无可提取文本
数据库连接失败
```

不得显示“上传成功”。

---

### 7.8 文档筛选区

调用接口：

```http
GET /api/knowledge/documents
```

筛选项：

| 字段 | 组件 | 说明 |
|---|---|---|
| keyword | Input | 文档标题关键词 |
| manufacturer | Select | 华为 / 阳光电源 |
| product_series | Select | SUN2000 / FusionSolar / SG |
| document_type | Select | 文档类型 |
| parse_status | Select | 解析状态 |
| page/page_size | Pagination | 分页 |

---

### 7.9 文档列表表格字段

| 列名 | 字段 | 显示方式 |
|---|---|---|
| 标题 | title | 文本 |
| 厂家 | manufacturer | 华为 / 阳光电源 |
| 产品系列 | product_series | 文本 |
| 设备类型 | device_type | 光伏逆变器 |
| 文档类型 | document_type | 标签 |
| 文件名 | file_name | 文本 |
| 文件大小 | file_size | 格式化 KB/MB |
| 解析状态 | parse_status | 状态标签 |
| 切片数 | chunk_count | 数字 |
| 创建时间 | created_at | 日期 |
| 操作 | - | 查看切片 / 详情 / 删除 / 重解析 |

---

### 7.10 切片查看

点击“查看切片”调用：

```http
GET /api/knowledge/documents/{document_id}/chunks
```

建议使用 Drawer 展示。

字段：

| 字段 | 显示 |
|---|---|
| chunk_index | 切片序号 |
| section_title | 章节标题 |
| content | 切片内容 |
| char_count | 字符数 |
| page_number | 页码 |
| embedding_status | 向量化状态 |
| created_at | 创建时间 |

---

### 7.11 文档删除

如实现删除按钮，调用：

```http
DELETE /api/knowledge/documents/{document_id}
```

交互要求：

```text
1. 必须二次确认
2. 提示删除后不再参与检索
3. 删除成功后刷新列表
```

---

### 7.12 空状态

当没有文档时，展示：

```text
暂无知识库资料。请先上传华为 SUN2000 或阳光电源 SG 系列光伏逆变器手册、告警代码或检修规程。
```

---

### 7.13 验收标准

```text
1. 可上传 txt/md/pdf/docx
2. 必须填写 manufacturer
3. device_type 默认为 pv_inverter
4. 上传后 parse_status = parsed
5. chunk_count > 0
6. 列表能按厂家筛选
7. 能查看真实切片
8. 不支持文件类型有错误提示
9. 空文件有错误提示
```

---

## 8. RetrievalChatView 检修问答页

---

### 8.1 页面目标

检修问答页用于让运维人员输入检修问题，系统从真实知识库切片中检索相关内容，生成带来源依据的检修回答。

页面不是普通聊天软件，而是：

```text
检修知识检索工作台
```

---

### 8.2 页面结构

建议结构：

```text
1. 问题输入区
2. 筛选条件区
3. 回答结果区
4. 建议步骤区
5. 来源依据区
6. 检索片段区
7. 问答记录提示
```

---

### 8.3 问题输入区

调用接口：

```http
POST /api/retrieval/query
```

字段：

| 字段 | 组件 | 必填 | 说明 |
|---|---|---:|---|
| query | Textarea | 是 | 用户问题 |
| manufacturer | Select | 否 | 华为 / 阳光电源 |
| product_series | Select | 否 | SUN2000 / FusionSolar / SG |
| device_type | Select | 否 | 默认 pv_inverter |
| document_type | Select | 否 | 文档类型过滤 |
| top_k | InputNumber | 否 | 默认 5，最大 10 |

---

### 8.4 推荐问题模板

页面可提供快捷问题按钮：

```text
华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？
阳光 SG 系列逆变器过温降额怎么处理？
逆变器通信中断但现场运行正常，应该如何判断？
光伏逆变器 MPPT 异常导致功率偏低，应该检查哪些项目？
逆变器并网失败可能有哪些原因？
```

点击模板后填入问题输入框。

---

### 8.5 提交交互

点击“开始检索”后：

```text
1. 按钮进入 loading
2. 禁止重复提交
3. 调用 /api/retrieval/query
4. 成功后展示回答
5. 失败后展示错误
```

如果问题为空：

```text
请输入检修问题或告警现象。
```

---

### 8.6 回答结果区

展示字段：

| 字段 | 说明 |
|---|---|
| answer | 系统回答 |
| confidence | 可信度 |
| trace_id | 追溯编号 |
| query_analysis | 可选，展示匹配关键词 |

可信度展示建议：

```text
0.75 以上：较高
0.50 - 0.75：中等
0.20 - 0.50：较低
```

不要显示为“准确率”。

---

### 8.7 建议步骤区

展示 `suggested_steps`。

推荐用：

```text
步骤条 Timeline
或编号列表
```

步骤通常包括：

```text
安全确认
告警信息核对
设备状态检查
关键部件排查
处理措施确认
复检与记录归档
```

---

### 8.8 来源依据区 references

必须清晰展示 references。

表格字段：

| 列名 | 字段 |
|---|---|
| 文档标题 | document_title |
| 厂家 | manufacturer |
| 产品系列 | product_series |
| 文档类型 | document_type |
| 章节 | section_title |
| 切片序号 | chunk_index |
| 页码 | page_number |
| 来源 | source |
| 相关度 | score |

如果 references 为空，显示：

```text
当前知识库未检索到足够相关资料，请补充华为或阳光电源逆变器手册、告警代码或检修规程。
```

不得编造来源。

---

### 8.9 检索片段区 retrieved_chunks

建议使用折叠面板。

每个面板标题：

```text
[score] 文档标题 - 章节标题
```

内容显示：

```text
content
```

如果片段过长，可默认折叠，允许展开。

---

### 8.10 生成检修任务入口

当回答生成成功后，可提供按钮：

```text
基于该回答创建检修任务
```

点击后跳转到 `MaintenanceTaskView`，并预填：

```text
manufacturer
product_series
device_type
fault_description
source_type = qa
source_trace_id = trace_id
suggested_steps
```

第一版如暂未实现跨页预填，可先预留按钮但不强制。

---

### 8.11 验收标准

```text
1. 能输入问题并调用 /api/retrieval/query
2. 能按 manufacturer 过滤
3. 能按 product_series 过滤
4. 能展示 answer
5. 能展示 suggested_steps
6. 能展示真实 references
7. 能展示 retrieved_chunks
8. 无 references 时不编造来源
9. trace_id 可见
10. 每次问答后 qa_records 可查询
```

---

## 9. FaultDiagnosisView 故障辅助诊断页

---

### 9.1 页面目标

故障诊断页用于输入逆变器故障现象、告警代码和运行状态，生成初步原因分析、排查步骤、安全提示和推荐处理措施。

---

### 9.2 页面结构

建议结构：

```text
1. 故障输入表单
2. 诊断按钮
3. 可能原因区
4. 排查步骤区
5. 安全注意事项区
6. 推荐处理措施区
7. 来源依据区
8. 创建检修任务入口
```

---

### 9.3 诊断表单字段

调用接口：

```http
POST /api/diagnosis/analyze
```

| 字段 | 组件 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| manufacturer | Select | 否 | huawei | 华为/阳光电源 |
| product_series | Select | 否 | 根据厂家 | SUN2000/FusionSolar/SG |
| device_type | Select | 是 | pv_inverter | 光伏逆变器 |
| device_name | Input | 否 | 空 | 设备名称 |
| model | Input | 否 | 空 | 型号 |
| fault_type | Select | 否 | 空 | 故障类型 |
| alarm_code | Input | 否 | 空 | 告警代码 |
| alarm_info | Textarea | 否 | 空 | 告警信息 |
| fault_description | Textarea | 是 | 无 | 故障现象 |
| device_status | Select | 否 | warning | normal/warning/fault/offline |
| include_references | Switch | 否 | true | 是否检索来源 |

---

### 9.4 推荐诊断场景

可提供快捷填充：

```text
华为 SUN2000 绝缘阻抗低
阳光 SG 系列过温降额
逆变器通信中断
逆变器并网失败
MPPT 异常导致功率偏低
设备离线但现场无明显异常
```

---

### 9.5 诊断结果展示

接口返回字段：

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

展示建议：

| 区域 | 组件 |
|---|---|
| 可能原因 | Card + List |
| 排查步骤 | Timeline |
| 安全注意事项 | Alert / Warning Card |
| 推荐处理措施 | List |
| 来源依据 | ReferenceList 表格 |
| trace_id | 小号文本 / Tag |

---

### 9.6 安全提示区必须突出

光伏逆变器涉及电气安全，安全提示不能和普通建议混在一起。

建议使用醒目 Alert：

```text
涉及直流侧、交流侧、开盖检查、绝缘测试等操作时，必须由具备资质的人员按照厂家手册和电站安全规程执行。
```

---

### 9.7 诊断失败状态

失败时显示：

```text
诊断失败，请检查后端服务、数据库连接或输入参数。
```

不得展示固定假结果。

---

### 9.8 创建任务入口

诊断成功后提供：

```text
生成检修任务
```

预填：

```text
title
manufacturer
product_series
device_type
fault_type
alarm_code
fault_description
priority
source_type = diagnosis
source_trace_id = trace_id
suggested_steps = inspection_steps
```

---

### 9.9 验收标准

```text
1. fault_description 必填
2. 能返回 possible_causes
3. 能返回 inspection_steps
4. 能返回 safety_notes
5. 能返回 recommended_actions
6. diagnosis_records 真实写入
7. trace_id 可见
8. references 如存在必须真实
9. 安全提示醒目展示
```

---

## 10. MaintenanceTaskView 检修任务页

---

### 10.1 页面目标

检修任务页用于管理由人工、问答或诊断生成的检修任务。

---

### 10.2 页面结构

建议：

```text
1. 任务创建按钮
2. 筛选区
3. 任务列表表格
4. 任务详情抽屉
5. 状态更新弹窗
```

---

### 10.3 创建任务表单

调用：

```http
POST /api/maintenance/tasks
```

字段：

| 字段 | 组件 | 必填 | 默认值 |
|---|---|---:|---|
| title | Input | 是 | 无 |
| manufacturer | Select | 否 | huawei |
| product_series | Select | 否 | SUN2000 |
| device_type | Select | 是 | pv_inverter |
| device_name | Input | 否 | 空 |
| model | Input | 否 | 空 |
| fault_type | Select | 否 | 空 |
| alarm_code | Input | 否 | 空 |
| fault_description | Textarea | 否 | 空 |
| priority | Select | 否 | medium |
| assignee | Input | 否 | 空 |
| due_date | DateTimePicker | 否 | 空 |
| source_type | Select | 否 | manual |
| source_trace_id | Input | 否 | 空 |
| suggested_steps | Dynamic List / Textarea | 否 | [] |

---

### 10.4 任务筛选区

调用：

```http
GET /api/maintenance/tasks
```

筛选项：

```text
manufacturer
product_series
fault_type
priority
task_status
assignee
keyword
```

---

### 10.5 任务表格字段

| 列名 | 字段 |
|---|---|
| 任务标题 | title |
| 厂家 | manufacturer |
| 产品系列 | product_series |
| 故障类型 | fault_type |
| 优先级 | priority |
| 状态 | task_status |
| 负责人 | assignee |
| 来源 | source_type |
| 创建时间 | created_at |
| 操作 | 查看 / 更新状态 |

---

### 10.6 状态更新

调用：

```http
POST /api/maintenance/tasks/{task_id}/start
POST /api/maintenance/tasks/{task_id}/complete
POST /api/maintenance/tasks/{task_id}/cancel
```

支持状态：

```text
pending
in_progress
completed
cancelled
```

完成任务时建议要求填写：

```text
result_summary
completion_notes
```

非法流转后端返回 409，前端应显示错误。

---

### 10.7 任务详情

展示：

```text
title
manufacturer
product_series
device_name
fault_type
alarm_code
fault_description
priority
task_status
assignee
source_type
source_trace_id
suggested_steps
result_summary
completion_notes
created_at
updated_at
completed_at
```

如果 `source_trace_id` 存在，可提示：

```text
该任务来源于一次检修问答或故障诊断，可在记录追溯中查看完整来源。
```

---

### 10.8 验收标准

```text
1. 能创建任务
2. task_status 默认 pending
3. 能查询任务列表
4. 能查看任务详情
5. 能更新状态
6. 完成任务时能保存 result_summary
7. manufacturer/product_series 保存正确
8. 数据刷新后任务不丢失
```

---

## 11. RecordCenterView 记录追溯页

---

### 11.1 页面目标

记录追溯页用于查看检修问答记录和故障诊断记录。

这是区别普通聊天系统的重要页面。

---

### 11.2 页面结构

建议使用 Tabs：

```text
Tab 1：问答记录
Tab 2：诊断记录
```

---

### 11.3 问答记录 Tab

调用：

```http
GET /api/retrieval/records
```

筛选项：

```text
manufacturer
product_series
device_type
keyword
trace_id
date_range
```

表格字段：

| 列名 | 字段 |
|---|---|
| 问题 | question |
| 厂家 | manufacturer |
| 产品系列 | product_series |
| 可信度 | confidence |
| 追溯编号 | trace_id |
| 创建时间 | created_at |
| 操作 | 查看详情 |

详情抽屉展示：

```text
question
answer
suggested_steps
references
retrieved_chunks
trace_id
created_at
```

---

### 11.4 诊断记录 Tab

调用：

```http
GET /api/diagnosis/records
```

筛选项：

```text
manufacturer
product_series
fault_type
alarm_code
trace_id
date_range
```

表格字段：

| 列名 | 字段 |
|---|---|
| 故障描述 | fault_description |
| 厂家 | manufacturer |
| 产品系列 | product_series |
| 故障类型 | fault_type |
| 告警代码 | alarm_code |
| 可信度 | confidence |
| 追溯编号 | trace_id |
| 创建时间 | created_at |
| 操作 | 查看详情 |

详情展示：

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
trace_id
created_at
```

---

### 11.5 空状态

问答记录为空：

```text
暂无检修问答记录。请先在检修问答页面提交问题。
```

诊断记录为空：

```text
暂无故障诊断记录。请先在故障诊断页面提交故障现象。
```

---

### 11.6 验收标准

```text
1. 能查询 qa_records
2. 能查询 diagnosis_records
3. trace_id 可见
4. references 可见
5. suggested_steps / inspection_steps 可见
6. 数据来自 PostgreSQL
7. 刷新后记录不丢失
```

---

## 12. SystemStatusView 系统状态页

---

### 12.1 页面目标

系统状态页用于展示后端、数据库、知识库统计和运行环境。

---

### 12.2 页面接口

调用：

```http
GET /api/health
GET /api/system/status
GET /api/system/info
```

---

### 12.3 展示内容

| 模块 | 展示字段 |
|---|---|
| 服务状态 | name, status, version, environment |
| 数据库状态 | database_status |
| 知识库统计 | document_count, chunk_count |
| 记录统计 | qa_record_count, diagnosis_record_count |
| 任务统计 | maintenance_task_count |
| 部署目标 | LoongArch + Kylin |
| 技术栈 | FastAPI, Vue3, PostgreSQL |

---

### 12.4 异常状态

如果数据库不可用：

```text
数据库连接异常，请检查 DATABASE_URL、PostgreSQL 服务和 Alembic 迁移状态。
```

如果后端不可用：

```text
后端服务不可访问，请检查 FastAPI 服务是否启动。
```

不得显示 connected。

---

### 12.5 验收标准

```text
1. /api/health 可展示
2. /api/system/status 可展示
3. 数据库断开时有明确提示
4. 统计数据来自 PostgreSQL
5. 部署目标显示 LoongArch + Kylin 原生部署
```

---

## 13. LoginView 登录页

第一版可保留静态登录页，不强制实现完整鉴权。

### 13.1 页面目标

用于后续权限系统预留。

### 13.2 第一版要求

```text
1. 页面文案符合 Energy-Maintenance 定位
2. 不出现教育系统、通用后台、车辆维修字样
3. 登录按钮可进入 Dashboard
4. 明确标注当前为演示登录或开发模式
```

### 13.3 后续增强

后续可接入：

```text
JWT
用户角色
权限控制
操作日志
```

---

## 14. 通用组件规范

### 14.1 StatusTag

用于展示：

```text
parse_status
task_status
priority
database_status
```

必须统一颜色，避免各页面状态颜色不一致。

---

### 14.2 ReferenceList

用于展示 references。

应复用在：

```text
RetrievalChatView
FaultDiagnosisView
RecordCenterView
```

字段必须包含：

```text
document_title
manufacturer
product_series
document_type
section_title
chunk_index
page_number
source
score
```

---

### 14.3 EmptyState

用于空数据提示。

空状态文案必须具体，例如：

```text
暂无华为或阳光电源逆变器资料，请先上传设备手册、告警代码或检修规程。
```

不要只写：

```text
暂无数据
```

---

## 15. 加载、错误与空状态规范

### 15.1 加载状态

所有异步请求应有 loading 状态：

```text
上传中
解析中
检索中
诊断中
加载列表中
保存任务中
```

---

### 15.2 错误状态

错误提示应使用后端 message。

例如：

```text
上传失败：Unsupported document extension: exe
检索失败：query or question must not be empty
数据库连接异常：请检查 PostgreSQL 服务
```

---

### 15.3 空状态

空状态必须给出下一步建议。

例如：

```text
当前知识库未检索到相关资料，请上传华为 SUN2000 或阳光 SG 系列逆变器资料后重试。
```

---

## 16. 前端真实闭环验收

第一版前端必须支持以下真实闭环：

```text
1. 打开 SystemStatusView，确认后端和数据库状态
2. 在 KnowledgeBaseView 上传华为样例文档
3. 查看文档 parse_status = parsed
4. 查看知识切片 content
5. 在 RetrievalChatView 提问华为 SUN2000 绝缘阻抗低排查
6. 展示 answer、references、retrieved_chunks
7. 在 RecordCenterView 查看本次 qa_record
8. 在 FaultDiagnosisView 输入阳光 SG 过温故障
9. 展示 possible_causes、inspection_steps、safety_notes
10. 在 MaintenanceTaskView 创建并更新任务
```

如果任何一步只显示模拟数据，不能认定为验收通过。

---

## 17. 前端禁止事项

前端开发禁止：

```text
1. 将系统写成普通聊天软件
2. 页面文案泛化为所有新能源设备
3. 暴露第一版不支持的设备类型
4. 接口失败后显示成功
5. 编造 references
6. 不显示 trace_id
7. 不显示数据库异常
8. 在页面中硬编码大量假业务数据
9. 把 API 路径写成公开版本化 API 前缀而后端是 /api
10. 引入与项目无关的大型 UI 风格或功能
```

---

## 18. 与其他文档关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
03_database_schema_design.md
04_api_contract_design.md
```

其中：

- `01` 定义项目范围；
- `02` 定义技术架构；
- `03` 定义数据库字段；
- `04` 定义接口契约；
- `05` 定义前端页面和交互。

后续文档如知识库处理、RAG 问答、测试验收、vibe coding 任务计划必须与本文档保持一致。

---

## 19. 下一步建议

本文档确认后，下一份建议编写：

```text
06_knowledge_base_and_document_processing_spec.md
```

下一份文档应重点明确：

```text
文件上传规则
解析器选择
文本清洗策略
切片策略
parse_status 状态流转
chunk 字段生成
华为/阳光样例资料准备
上传安全
解析失败处理
知识库真实入库验收
```
---

## Task 02A 前端页面一致性补充

第一版本前端应聚焦华为、阳光电源光伏逆变器检修场景，不扩展为通用新能源设备平台。

### A. P0 页面清单

后续功能设计和实现应覆盖以下页面：

- LoginView。
- DashboardView。
- UserManagementView。
- DeviceLedgerView。
- DeviceDetailView。
- KnowledgeBaseView。
- KnowledgeReviewView。
- RetrievalChatView。
- FaultDiagnosisView。
- SOPGuideView。
- MaintenanceTaskView。
- TaskDetailView。
- RecordCenterView。
- ModelServiceView。
- SystemStatusView。

---

## Task 11 前端补充：记录中心与审核修正

Task 11 已补充以下前端页面与路由：

```text
/records -> RecordCenterView
/review  -> ReviewCenterView
```

### RecordCenterView

记录中心页调用：

```text
GET /api/record-center/overview
GET /api/record-center/search
GET /api/record-center/records/{record_type}/{record_id}
GET /api/record-center/devices/{device_id}/timeline
```

---

## Task 18K Final Frontend Route and API Calibration

The active frontend source tree is `frontend/`. The final installed static frontend is generated into `backend/static/frontend`.

Current delivery route mapping:

```text
/login                  -> Login
/dashboard              -> Dashboard
/device/*               -> device inventory, models, alarms
/knowledge/documents    -> knowledge documents
/knowledge/contributions -> knowledge contributions
/knowledge/graph        -> knowledge graph
/assistant/chat         -> retrieval QA
/diagnosis              -> fault diagnosis
/sop                    -> SOP center
/workorder/*            -> maintenance tasks
/trace                  -> record center / traceability
/review                 -> knowledge review
/review/corrections     -> model-output corrections
/media                  -> media evidence
/model-service          -> model gateway
/system                 -> system status
/system/users           -> user management
```

Frontend API calls should use the centralized Axios instance with `/api` as the base path. Do not use legacy record endpoints, the legacy maintenance-diagnosis endpoint name, or public versioned API-prefix examples in final UI documentation.

Capability boundary for UI copy:

- The UI may show cloud/local/OCR provider status as blocked, disabled, unavailable, or not configured.
- The UI must not claim real cloud model generation, local GGUF inference, OCR recognition, pgvector/embedding retrieval, image fault recognition, or LoongArch/Kylin real-machine deployment unless real verification has been completed.

页面通过设备下拉选择真实设备，不要求用户手动输入 `device_id`。记录详情通过表格点击进入，不要求用户手动输入 `record_id`、`trace_id` 或 `task_id`。

### ReviewCenterView

审核修正页包含两个区域：

```text
知识审核
输出修正
```

知识审核区域调用 `/api/review/knowledge` 系列接口。只有 `admin`、`expert` 显示审核通过、驳回、归档操作。

输出修正区域调用 `/api/corrections` 系列接口。提交修正前需从真实记录搜索结果中选择来源记录，不把内部 ID 作为主流程手填项。

### Dashboard / SystemStatusView

Dashboard 和 SystemStatusView 已接入：

```text
GET /api/system/statistics
GET /api/record-center/overview
```

用于展示设备、知识库、QA、诊断、任务、SOP、维修履历、媒体和修正记录的真实统计。

### B. 页面选项边界

第一版本制造商选项：

- huawei：华为。
- sungrow：阳光电源。

第一版本产品系列：

- SUN2000。
- FusionSolar。
- SG。

第一版本核心设备类型：

- pv_inverter：光伏逆变器。

历史接口中的 `inverter` 可兼容显示为光伏逆变器，但新页面、新筛选项和新增业务表单应优先使用 `pv_inverter`。

### C. 前端数据真实性要求

前端不得伪造上传成功、检索来源、数据库连接状态或系统运行状态。接口失败时应展示错误提示；无检索结果时应展示需要补充设备手册、告警代码、故障案例或巡检规范的提示。
---

## Task 18B Frontend Addendum: 一线经验贡献页

New route:

```text
/knowledge/contributions
```

Page responsibilities:

- engineer/admin/expert can create a contribution draft.
- engineer can edit own `draft`, `changes_requested`, or `rejected` contribution.
- engineer can submit to expert review.
- expert/admin can request changes, approve, reject, archive, and convert approved contribution to knowledge.
- viewer can list and open approved/converted contributions only, without write buttons.
- form fields include manufacturer, product series, device, fault type, alarm code, symptom, process, root cause, solution, tools, parts, safety notes, related diagnosis/task/QA record, and media IDs.
- device, task, diagnosis, and QA context must come from existing APIs, not manual UUID input.
- associated media uses the existing authenticated media evidence picker and preview flow.

The page must keep first-version scope restricted to Huawei/Sungrow PV inverters and must not expose storage batteries, box transformers, or generic renewable equipment as first-version choices.

---

## Task 18C Knowledge Graph Page

Task 18C adds a `知识图谱` page under the knowledge module.

The page provides:

- graph overview cards
- node list and expert/admin manual node creation
- edge list and expert/admin manual edge creation
- rule-based extraction trigger from approved parsed knowledge documents
- pending candidate review for expert/admin
- extraction run and evidence link list
- read-only node neighborhood lookup

`viewer` can read graph data only. `expert` and `admin` can create graph data, run extraction, and review candidates. Task 18C provided the management interface; Task 18D adds lightweight graph visualization and business-context display without introducing a heavy visualization dependency.

---

## Task 18D Frontend Addendum: Knowledge Graph Visualization and Business Context

Task 18D enhances existing pages without changing the first-version business scope.

### Knowledge Graph Page

Route:

```text
/knowledge/graph
```

Additions:

- graph visualization tab using active graph nodes and edges from `/api/kg/graph`.
- filters for manufacturer, product series, fault type, node type, and keyword.
- node click displays node details and real evidence links.
- edge click displays edge details and real evidence links.
- neighborhood expansion around a selected node.
- path query tab using `/api/kg/path`.
- graph legend for node and relation types.

The visualization is intentionally lightweight. It does not introduce Neo4j, Cytoscape, ECharts graph, Three.js, pgvector, embedding, or OCR.

### Retrieval Assistant

The retrieval assistant may expose an `enable_kg_enhancement` switch. When enabled, returned graph context is shown as:

- matched graph nodes
- related causes/actions/safety risks
- graph paths
- real graph evidence

If no graph context is returned, the page should state that no relevant active graph context was found rather than fabricate sources.

### Fault Diagnosis

The diagnosis page may expose an `enable_kg_enhancement` switch. When enabled, returned graph context is shown as:

- related causes
- inspection items
- recommended actions
- safety risks
- graph evidence

Graph content is supplemental and must not replace field-engineer judgment or manufacturer manuals.

### SOP Generation

The SOP page may expose an `enable_kg_enhancement` switch. When enabled, returned graph context is shown as:

- tools
- parts
- safety risks
- related graph steps
- graph evidence

Template and rule-based SOP structure remains the mainline. Graph context is supplementary.

### Record Center

Record detail pages may display saved `knowledge_graph` summaries when retrieval, diagnosis, SOP, node, or edge records have traceable graph evidence.

### Frontend Rules

- Do not submit translated UI labels as backend enum values.
- Do not fabricate graph nodes, edges, references, or evidence in the frontend.
- `viewer` remains read-only.
- Expert/admin graph write actions remain role-gated by backend permissions.
## Task 22A Frontend API Addendum

Task 22A only adds frontend API/type wrappers for Agent Runtime. It does not add the full Agent Workbench page.

New files:

```text
frontend/src/api/agents.ts
frontend/src/types/agent.ts
```

Available frontend API functions:

- `getAgentDefinitions`
- `getAgentDefinition`
- `getAgentTools`
- `createAgentRun`
- `getAgentRuns`
- `getAgentRunDetail`
- `cancelAgentRun`
- `getAgentRunSteps`
- `getAgentRunToolCalls`
- `getAgentRunApprovals`
- `approveAgentApproval`
- `rejectAgentApproval`
- `getAgentArtifacts`
- `getAgentEvents`

The complete Agent Workbench UI remains reserved for a later task.
# Task 22B Frontend Contract Note

The frontend agent API wrapper now supports `tools`, `media_ids`, `tool_inputs`, and:

```text
POST /api/agents/runs/{run_id}/execute-tool
```

Task 22B does not add a full agent workbench page. It only updates frontend TypeScript types and API wrappers so later pages can display tool calls, draft artifacts, approvals, blocked tools, and manual single-tool execution results.

---

## Task 22C Frontend API Reservation

Task 22C adds frontend API client functions and types for `/api/external-apis`.

No full Provider Gateway page is introduced in this task. Future agent workspace pages can use:

- `getExternalApiProviders`
- `getExternalApiProvider`
- `getExternalApiRoutes`
- `getExternalApiStatus`
- `checkExternalApiProvider`
- `dryRunExternalApi`
- `getExternalApiLogs`
- `getExternalApiLogDetail`
- `getExternalApiHealthChecks`

Provider keys, model names, and trace IDs may be displayed as technical fields. Real API keys must never be displayed.

## Task 22D Multimodal Evidence API Reservation

Task 22D adds frontend API client functions and types for `/api/multimodal`.

No full multimodal evidence center page is introduced in this task. Future UI work can use:

- `getMediaJobs`
- `createMediaProcessingJob`
- `getProcessingJob`
- `cancelProcessingJob`
- `getMediaOcrResults`
- `getOcrResult`
- `getMediaAnalyses`
- `getAnalysis`
- `reviewAnalysis`
- `getEvidenceLinks`
- `createEvidenceLink`
- `getMediaMultimodalSummary`

Machine OCR and multimodal analysis outputs must be presented as auxiliary evidence, not as final fault conclusions.
## Task 22E Addendum: Adapter API Types

Frontend API wrappers reserve external adapter calls for future UI surfaces:

```text
dryRunExternalApi
mockRunExternalApi
createMediaProcessingJob
```

No full external-provider UI page is added in Task 22E. Any future UI must clearly label mock results as local verification output and must not display them as real machine-recognition success.

## Task 22F Frontend Interaction Update

Task 22F adds the page `/multimodal` named 多模态证据中心.

The page is placed near 媒体资料 and supports:

- provider status and dry-run/mock-run entry;
- media filtering and selection;
- processing job list;
- OCR dry-run, AI dry-run, OCR mock-run, and AI mock-run actions;
- OCR result and AI analysis display;
- expert/admin human review;
- evidence link creation;
- Agent Run dry-run entry with steps, tool calls, artifacts, and approvals display.

Viewer users can open the page but must remain read-only. The page must not show fake success if any backend API fails.
## Task 22G Addendum: Multimodal Evidence Agent Entry

The `/multimodal` page includes a controlled entry for `multimodal_evidence_agent`.

The page supports:

- selecting uploaded PV inverter media evidence;
- entering site description and observed fault symptoms;
- selecting the default tool chain: `media_lookup`, `media_ocr`, `media_mimo_analysis`, `safety_guard`;
- toggling dry-run and mock-run mode;
- creating a multimodal evidence agent run;
- displaying timeline, tool calls, artifacts, safety checklist, evidence links, and final answer.

Role behavior:

- viewer: read-only, create controls disabled or hidden;
- engineer: dry-run only;
- expert/admin: dry-run and mock-run, plus review actions.

Technical identifiers such as `run_id`, `trace_id`, provider codes, and model names may remain visible as technical fields. User-facing status, safety, and evidence summaries should be presented in Chinese.

## Task 22H Addendum: Agent Workbench

Task 22H adds the route:

```text
/agents/workbench
```

Page name:

```text
智能体工作台
```

The page provides a controlled frontend entry for:

- `multimodal_evidence_agent`
- `fault_diagnosis_agent`
- `sop_planner_agent`
- `task_orchestration_agent`

Required interactions:

- choose an agent;
- choose a PV inverter device;
- choose media evidence where available;
- enter fault symptoms, alarm code, manufacturer, product series, and fault type;
- choose dry-run / mock-run mode according to role permissions;
- create an agent run;
- display final answer, timeline, steps, tool calls, artifacts, approvals, and safety checklist;
- display `diagnosis_summary`, `sop_draft`, and `task_draft` with business-readable panels;
- allow expert/admin users to approve or reject pending draft approvals.

Role behavior:

- viewer: read-only; cannot create runs or approve/reject drafts;
- engineer: can create dry-run runs;
- expert/admin: can create permitted runs and review draft approvals.

The page must not show generated drafts as formal work orders or executed SOP records. All high-risk outputs remain draft artifacts plus human approval.

## Task 22I Addendum: Knowledge Curator Agent Entry

The `/agents/workbench` page includes a controlled entry for `knowledge_curator_agent`.

The page supports:

- selecting the knowledge curator agent;
- selecting a Huawei/Sungrow PV inverter device;
- selecting related media evidence where available;
- entering fault symptoms, alarm code, manufacturer, product series, fault type, and engineer notes;
- entering source Agent Run IDs and source Artifact IDs from diagnosis, SOP, task, or multimodal evidence runs;
- creating a dry-run knowledge curation run;
- displaying `maintenance_case_summary`, `knowledge_contribution_draft`, `kg_candidate_suggestion`, `evidence_trace_summary`, and `safety_checklist`;
- displaying duplicate-risk, mocked-evidence, unreviewed-AI-evidence, limitation, and source-tracing information where returned by the backend;
- allowing expert/admin users to approve or reject the pending knowledge-contribution draft approval.

## Task 22J Addendum: Agent Artifact Conversion Panel

The `/agents/workbench` page includes a controlled conversion panel for approved draft artifacts.

The panel appears when the current Agent Run contains one of:

- `knowledge_contribution_draft`
- `sop_draft`
- `task_draft`
- `kg_candidate_suggestion`

Required behavior:

- show the conversion target type for each convertible artifact;
- show approval status and converted target ID where available;
- disable conversion until the matching approval is `approved`;
- hide conversion buttons from `viewer` and `engineer` users;
- allow `expert` users to convert approved non-risky drafts;
- allow `admin` users to use `override_warnings` for mocked or unreviewed evidence;
- refresh timeline and conversion status after a successful conversion;
- never display a draft as a formal business object before the backend conversion API succeeds.

The frontend must keep API enum values in English and submit them unchanged:

```text
knowledge_contribution
sop_template
maintenance_task
kg_candidate
```

The panel does not create documents, chunks, SOP execution records, completed maintenance records, or formal graph nodes/edges in the frontend.

Role behavior:

- viewer: read-only; cannot create runs or approve/reject drafts;
- engineer: can create dry-run curator runs;
- expert/admin: can create permitted runs and review draft approvals.

The page must not present generated drafts as formal knowledge-base contributions, formal documents, approved chunks, or formal knowledge-graph records. Formal conversion from an approved draft is reserved for Task 22J.
## Task 24B Addendum: DashVector Hybrid Retrieval UI

Frontend pages may display vector-index status and hybrid retrieval diagnostics, but must label `fake_in_memory` and `deterministic_test` as local test modes. The UI must use `/api/vector-search` API functions, must not expose raw vectors or API keys, and must not present fake local testing as real DashVector online success.

## Task 24D Addendum: Security UI

The System Status page should display sanitized security status from `/api/system/status`, including production guard, CORS policy, request-size limits, rate limit, log-dir configuration, and warning messages. It must not display secret values, Authorization tokens, database passwords, local file paths, or raw provider keys.

Model, vector, multimodal, and external-provider views should keep blocked / not_configured / dry-run / fake_in_memory / deterministic_test labels visible in Chinese, so users do not mistake test-mode behavior for production online capability. Viewer users must remain read-only and should not see high-risk write or approval actions.

## Task 24E Addendum: Agent Conversion History UI

The Agent Workbench conversion panel should display conversion history from backend conversion APIs, including conversion status, `conversion_trace_id`, target id, completion/failure time, and failure reason. After a successful conversion, the same artifact and target must not show a second active conversion button.

Viewer and engineer accounts remain unable to convert artifacts. Expert/admin users may convert only after the matching approval is approved.
