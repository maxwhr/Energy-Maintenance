# 12 软件功能设计文档

**文档名称：** `12_functional_design_specification.md`  
**项目名称：** Energy-Maintenance  
**中文定位：** 面向华为与阳光电源光伏逆变器的多模态大模型检修知识检索、故障诊断与标准化作业辅助系统  
**文档版本：** v2.0  
**文档状态：** 功能边界确认版  
**适用阶段：** 数据库增强 / 后端接口 / 前端页面 / 测试验收设计  
**第一版范围：** 华为 SUN2000 / FusionSolar 与阳光电源 SG 系列光伏逆变器检修场景  

---

## 1. 文档目的

本文档在《11 软件功能需求分析文档》的基础上，对 Energy-Maintenance 第一版功能进行设计拆解，明确系统模块、页面结构、接口边界、数据流、权限设计、数据库支撑关系和阶段化实现方案。

本文档用于指导后续 Codex 开发任务，尤其是：

```text
1. 数据库模型与 migration 增强；
2. FastAPI 后端接口设计；
3. Vue3 前端页面设计；
4. 本地/云端模型服务接入；
5. 多模态知识库与检索链路；
6. 设备台账、维修履历和任务闭环；
7. 知识审核与模型输出修正；
8. 测试用例和验收报告编写。
```

---

## 2. 系统总体功能架构

Energy-Maintenance 第一版采用 B/S 架构，整体由前端 Web、后端 API、PostgreSQL 数据库、文件存储、本地模型服务和可选云端模型服务组成。

### 2.1 功能架构图

```text
用户浏览器
    ↓
Vue3 Web 前端
    ↓
FastAPI 后端 API
    ↓
业务服务层
    ├── AuthService
    ├── DeviceService
    ├── KnowledgeService
    ├── RetrievalService
    ├── ModelGateway
    ├── DiagnosisService
    ├── SOPService
    ├── TaskService
    ├── ReviewService
    └── RecordService
    ↓
Repository 数据访问层
    ↓
PostgreSQL
    ↓
知识文档、设备台账、维修履历、问答记录、诊断记录、任务记录、审核记录
```

### 2.2 模型服务架构

```text
ModelGateway
    ├── LocalModelAdapter
    │       └── LoongArch + Kylin 本地小模型服务
    └── CloudModelAdapter
            └── Qwen / DeepSeek / OpenAI-compatible API
```

模型调用统一通过 ModelGateway，不允许业务模块直接调用某个模型 SDK。

### 2.3 多模态处理架构

```text
文本资料
    ↓
DocumentParser
    ↓
TextSplitter
    ↓
KnowledgeChunks

故障图片
    ↓
MediaUploadService
    ↓
人工图片说明 / 可选 OCR
    ↓
ImageDescriptionText
    ↓
Knowledge / Diagnosis / Task 关联

设备型号 / 告警码
    ↓
Structured Query
    ↓
过滤与精确匹配
```

第一版多模态以“文本 + 设备型号 + 告警码 + 故障图片 + 图片说明”为核心。

---

## 3. 前端页面设计

第一版建议设置以下主菜单：

```text
1. 工作台
2. 用户与权限
3. 设备台账
4. 知识库
5. 智能检索
6. 故障诊断
7. 作业指引
8. 检修任务
9. 记录追溯
10. 知识审核
11. 系统管理
```

### 3.1 页面与路由

| 页面 | 路由 | 说明 |
|---|---|---|
| LoginView | `/login` | 用户登录 |
| DashboardView | `/dashboard` | 工作台与数据概览 |
| UserManagementView | `/users` | 用户与权限管理 |
| DeviceLedgerView | `/devices` | 设备台账 |
| DeviceDetailView | `/devices/:id` | 设备详情与维修履历 |
| KnowledgeBaseView | `/knowledge` | 多模态知识库 |
| KnowledgeReviewView | `/knowledge/review` | 知识审核 |
| RetrievalChatView | `/retrieval` | 智能检索与问答 |
| FaultDiagnosisView | `/diagnosis` | 故障辅助诊断 |
| SOPGuideView | `/sop` | 标准化作业指引 |
| MaintenanceTaskView | `/tasks` | 检修任务 |
| TaskDetailView | `/tasks/:id` | 任务详情与执行 |
| RecordCenterView | `/records` | 记录追溯 |
| ModelServiceView | `/models` | 模型服务管理 |
| SystemStatusView | `/status` | 系统状态 |

### 3.2 菜单权限

| 菜单 | admin | expert | engineer | viewer |
|---|---|---|---|---|
| 工作台 | 是 | 是 | 是 | 是 |
| 用户与权限 | 是 | 否 | 否 | 否 |
| 设备台账 | 是 | 是 | 是 | 是 |
| 知识库 | 是 | 是 | 是 | 是 |
| 智能检索 | 是 | 是 | 是 | 是 |
| 故障诊断 | 是 | 是 | 是 | 是 |
| 作业指引 | 是 | 是 | 是 | 是 |
| 检修任务 | 是 | 是 | 是 | 只读 |
| 记录追溯 | 是 | 是 | 是 | 是 |
| 知识审核 | 是 | 是 | 否 | 否 |
| 系统管理 | 是 | 是/只读 | 否 | 否 |

---

## 4. 后端模块设计

推荐后端目录结构：

```text
backend/app/
├── api/
│   └── routes/
│       ├── auth.py
│       ├── users.py
│       ├── devices.py
│       ├── knowledge.py
│       ├── retrieval.py
│       ├── diagnosis.py
│       ├── sop.py
│       ├── tasks.py
│       ├── records.py
│       ├── reviews.py
│       ├── models.py
│       └── system.py
├── core/
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   └── permissions.py
├── models/
├── schemas/
├── repositories/
├── services/
├── knowledge/
├── retrieval/
├── maintenance/
├── model_gateway/
├── media/
└── utils/
```

分层原则：

```text
api -> service -> repository -> model
```

禁止在 API 层直接写复杂数据库逻辑。

---

## 5. 模块一：登录与权限管理

### 5.1 页面

```text
LoginView
UserManagementView
```

### 5.2 数据表

```text
users
```

### 5.3 主要字段

```text
id
username
password_hash
display_name
role
status
last_login_at
created_at
updated_at
```

### 5.4 接口设计

```http
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
GET /api/users
POST /api/users
PATCH /api/users/{user_id}
PATCH /api/users/{user_id}/status
PATCH /api/users/{user_id}/role
```

### 5.5 权限控制

后端应提供：

```text
get_current_user
require_role
require_any_role
```

前端应在路由守卫和菜单渲染中使用角色信息。

### 5.6 完成标准

```text
1. admin 可以创建用户。
2. 登录后返回 token。
3. 受保护接口必须携带 token。
4. viewer 无法访问写操作。
```

---

## 6. 模块二：工作台

### 6.1 页面

```text
DashboardView
```

### 6.2 统计数据

```text
device_count
fault_device_count
maintenance_task_count
active_task_count
knowledge_document_count
knowledge_chunk_count
pending_review_count
qa_record_count
diagnosis_record_count
local_model_status
database_status
```

### 6.3 接口

```http
GET /api/system/dashboard
GET /api/system/status
```

### 6.4 完成标准

```text
统计数据来自 PostgreSQL，不能使用前端写死数据。
```

---

## 7. 模块三：设备台账与维修履历

### 7.1 页面

```text
DeviceLedgerView
DeviceDetailView
```

### 7.2 数据表

```text
devices
device_maintenance_records
maintenance_tasks
diagnosis_records
qa_records
uploaded_media
```

### 7.3 设备台账接口

```http
POST /api/devices
GET /api/devices
GET /api/devices/{device_id}
PATCH /api/devices/{device_id}
DELETE /api/devices/{device_id}
GET /api/devices/{device_id}/history
GET /api/devices/{device_id}/tasks
GET /api/devices/{device_id}/diagnosis-records
```

### 7.4 维修履历接口

```http
POST /api/devices/{device_id}/maintenance-records
GET /api/devices/{device_id}/maintenance-records
GET /api/maintenance-records/{record_id}
PATCH /api/maintenance-records/{record_id}
```

### 7.5 复发判断设计

诊断时通过以下条件查询历史记录：

```text
device_id 相同
fault_type 相同
alarm_code 相同
fault_description 关键词相似
近 30 / 90 / 180 天出现过类似记录
```

返回：

```text
related_history
is_possible_recurrence
last_repair_action
last_verification_result
```

### 7.6 完成标准

```text
1. 设备详情页展示维修履历时间线。
2. 故障诊断可引用历史维修记录。
3. 任务完成后可生成维修履历。
```

---

## 8. 模块四：多模态知识库管理

### 8.1 页面

```text
KnowledgeBaseView
KnowledgeReviewView
```

### 8.2 数据表

```text
knowledge_documents
knowledge_chunks
uploaded_media
knowledge_contributions
knowledge_review_records
```

### 8.3 文档上传接口

```http
POST /api/knowledge/documents/upload
GET /api/knowledge/documents
GET /api/knowledge/documents/{document_id}
GET /api/knowledge/documents/{document_id}/chunks
DELETE /api/knowledge/documents/{document_id}
POST /api/knowledge/documents/{document_id}/reparse
```

### 8.4 多模态媒体接口

```http
POST /api/media/upload
GET /api/media
GET /api/media/{media_id}
DELETE /api/media/{media_id}
```

媒体字段：

```text
file_name
file_path
file_ext
mime_type
file_size
media_type
device_id
task_id
diagnosis_record_id
description
ocr_text
status
uploaded_by
```

### 8.5 文档解析设计

支持：

```text
txt：直接读取
md：直接读取
pdf：pypdf
docx：python-docx
```

第一版图片处理：

```text
图片上传
人工描述
可选 OCR
与设备/任务/诊断关联
图片描述进入检索
```

### 8.6 审核状态

```text
draft
pending_review
approved
rejected
archived
```

### 8.7 完成标准

```text
1. 文档上传后可解析切片。
2. 图片可上传并关联业务对象。
3. 未审核知识不进入正式检索。
```

---

## 9. 模块五：智能检索与大模型问答

### 9.1 页面

```text
RetrievalChatView
```

### 9.2 数据表

```text
knowledge_chunks
knowledge_documents
qa_records
model_call_logs
model_output_corrections
```

### 9.3 接口

```http
POST /api/retrieval/query
GET /api/retrieval/records
GET /api/retrieval/records/{trace_id}
POST /api/corrections
```

### 9.4 请求参数

```text
query
device_id
manufacturer
product_series
model
device_type
alarm_code
media_ids
image_description
document_type
top_k
model_provider
```

### 9.5 处理流程

```text
1. 校验用户输入。
2. 如果有 device_id，读取设备信息和历史维修记录。
3. 基于厂家、型号、告警码过滤知识切片。
4. 基于 query 和 image_description 检索知识。
5. 构造 references。
6. 通过 ModelGateway 调用本地或云端模型。
7. 生成 answer、suggested_steps、safety_notes。
8. 保存 qa_records。
9. 保存 model_call_logs。
```

### 9.6 返回结构

```json
{
  "answer": "...",
  "suggested_steps": [],
  "safety_notes": [],
  "references": [],
  "retrieved_chunks": [],
  "related_history": [],
  "model_provider": "local",
  "confidence": 0.72,
  "trace_id": "..."
}
```

### 9.7 完成标准

```text
1. references 来自真实 chunks。
2. qa_records 真实保存。
3. model_call_logs 真实保存。
4. 本地模型不可用时有明确错误或切换策略。
```

---

## 10. 模块六：故障辅助诊断

### 10.1 页面

```text
FaultDiagnosisView
```

### 10.2 数据表

```text
diagnosis_records
devices
device_maintenance_records
knowledge_chunks
uploaded_media
model_call_logs
```

### 10.3 接口

```http
POST /api/diagnosis/analyze
GET /api/diagnosis/records
GET /api/diagnosis/records/{trace_id}
POST /api/corrections
```

### 10.4 请求参数

```text
device_id
manufacturer
product_series
model
fault_type
alarm_code
alarm_info
fault_description
media_ids
image_description
device_status
model_provider
```

### 10.5 处理流程

```text
1. 校验 fault_description。
2. 读取设备台账。
3. 查询设备历史维修记录。
4. 检索相关知识切片。
5. 匹配规则型诊断模板。
6. 调用模型生成结构化诊断。
7. 输出可能原因、排查步骤、安全提示、推荐措施。
8. 保存 diagnosis_records。
```

### 10.6 返回结构

```json
{
  "possible_causes": [],
  "inspection_steps": [],
  "safety_notes": [],
  "recommended_actions": [],
  "related_history": [],
  "references": [],
  "confidence": 0.7,
  "trace_id": "..."
}
```

### 10.7 完成标准

```text
1. safety_notes 不为空。
2. 能引用历史维修记录。
3. 诊断记录可追溯。
4. 不输出“确定故障原因”的绝对结论。
```

---

## 11. 模块七：标准化作业指引 SOP

### 11.1 页面

```text
SOPGuideView
```

### 11.2 数据表

```text
sop_templates
sop_execution_records
maintenance_tasks
diagnosis_records
```

### 11.3 接口

```http
POST /api/sop/templates
GET /api/sop/templates
GET /api/sop/templates/{template_id}
PATCH /api/sop/templates/{template_id}
POST /api/sop/recommend
POST /api/sop/executions
GET /api/sop/executions/{execution_id}
PATCH /api/sop/executions/{execution_id}
```

### 11.4 SOP 模板字段

```text
title
manufacturer
product_series
device_type
fault_type
maintenance_level
steps
safety_requirements
tools_required
materials_required
compliance_notes
status
```

### 11.5 SOP 步骤结构

```json
[
  {
    "step_no": 1,
    "title": "作业前安全确认",
    "description": "确认作业票、PPE、停机状态。",
    "risk_level": "high",
    "must_confirm": true
  }
]
```

### 11.6 SOP 执行记录

```text
task_id
template_id
executor
step_results
abnormal_notes
started_at
completed_at
status
```

### 11.7 完成标准

```text
1. 可按故障类型推荐 SOP。
2. SOP 步骤可展示。
3. 执行结果可保存。
4. 高风险步骤必须有确认。
```

---

## 12. 模块八：检修任务与维修记录

### 12.1 页面

```text
MaintenanceTaskView
TaskDetailView
```

### 12.2 数据表

```text
maintenance_tasks
device_maintenance_records
sop_execution_records
uploaded_media
```

### 12.3 接口

```http
POST /api/maintenance/tasks
GET /api/maintenance/tasks
GET /api/maintenance/tasks/{task_id}
PUT /api/maintenance/tasks/{task_id}
POST /api/maintenance/tasks/{task_id}/start
POST /api/maintenance/tasks/{task_id}/cancel
POST /api/maintenance/tasks/{task_id}/complete
POST /api/media/upload
```

### 12.4 状态流转

```text
pending -> in_progress
pending -> cancelled
in_progress -> completed
in_progress -> cancelled
```

禁止：

```text
completed -> pending
cancelled -> in_progress
```

### 12.5 完成任务时必须填写

```text
result_summary
root_cause
repair_action
replaced_parts
verification_result
is_recurrent
completion_notes
```

### 12.6 完成标准

```text
1. 任务状态流转符合规则。
2. completed 任务自动或手动形成维修履历。
3. 任务详情能看到关联设备、SOP、诊断、图片和记录。
```

---

## 13. 模块九：知识投稿、审核与模型修正

### 13.1 页面

```text
KnowledgeReviewView
CorrectionReviewPanel
```

### 13.2 数据表

```text
knowledge_contributions
knowledge_review_records
model_output_corrections
knowledge_documents
knowledge_chunks
```

### 13.3 知识投稿接口

```http
POST /api/knowledge/contributions
GET /api/knowledge/contributions
GET /api/knowledge/contributions/{contribution_id}
PATCH /api/knowledge/contributions/{contribution_id}
POST /api/knowledge/contributions/{contribution_id}/submit
```

### 13.4 审核接口

```http
POST /api/knowledge/reviews/{contribution_id}/approve
POST /api/knowledge/reviews/{contribution_id}/reject
POST /api/knowledge/reviews/{contribution_id}/request-changes
```

### 13.5 模型修正接口

```http
POST /api/model-output-corrections
GET /api/model-output-corrections
GET /api/model-output-corrections/{correction_id}
POST /api/model-output-corrections/{correction_id}/submit
POST /api/model-output-corrections/{correction_id}/approve
```

### 13.6 处理流程

```text
工程师提交案例/经验/修正
    ↓
进入 pending_review
    ↓
专家审核
    ↓
通过后生成知识文档或知识切片
    ↓
参与后续检索
```

### 13.7 完成标准

```text
1. 投稿、审核、驳回可操作。
2. 审核记录可追溯。
3. 通过后的内容能进入知识库。
```

---

## 14. 模块十：记录追溯中心

### 14.1 页面

```text
RecordCenterView
```

### 14.2 追溯对象

```text
qa_records
diagnosis_records
maintenance_tasks
device_maintenance_records
knowledge_review_records
model_output_corrections
model_call_logs
operation_logs
```

### 14.3 接口

```http
GET /api/retrieval/records
GET /api/diagnosis/records
GET /api/record-center/overview
GET /api/record-center/search
GET /api/record-center/records/{record_type}/{record_id}
GET /api/record-center/devices/{device_id}/timeline
```

### 14.4 追溯链路

```text
一次故障诊断 trace_id
    ↓
关联设备 device_id
    ↓
关联历史维修记录
    ↓
关联 knowledge references
    ↓
关联 model_call_logs
    ↓
关联生成的 maintenance_task
    ↓
关联 sop_execution_record
    ↓
关联最终 device_maintenance_record
```

### 14.5 完成标准

```text
1. trace_id 可查询完整链路。
2. references 可查看。
3. 设备历史、任务、诊断和维修记录能关联展示。
```

---

## 15. 模块十一：系统管理与模型服务

### 15.1 页面

```text
SystemStatusView
ModelServiceView
```

### 15.2 接口

```http
GET /api/health
GET /api/system/info
GET /api/system/status
GET /api/models/status
GET /api/models/providers
PATCH /api/models/default-provider
GET /api/models/call-logs
```

### 15.3 系统状态字段

```text
service_status
database_status
local_model_status
cloud_model_status
default_model_provider
device_count
knowledge_document_count
knowledge_chunk_count
active_task_count
pending_review_count
qa_record_count
diagnosis_record_count
deployment_target
formal_database
```

### 15.4 完成标准

```text
1. 数据库状态真实。
2. 模型状态真实。
3. 统计数据真实。
4. 不显示假连接。
```

---

## 16. 数据库增强设计

Task 02 已有表：

```text
users
devices
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
operation_logs
model_call_logs
```

新版功能需要增强以下表：

```text
uploaded_media
device_maintenance_records
knowledge_contributions
knowledge_review_records
model_output_corrections
sop_templates
sop_execution_records
```

### 16.1 uploaded_media

用于保存故障图片、现场照片、文档附件等。

关键字段：

```text
id
file_name
file_path
file_ext
mime_type
file_size
media_type
description
ocr_text
device_id
task_id
diagnosis_record_id
qa_trace_id
uploaded_by
status
created_at
updated_at
```

### 16.2 device_maintenance_records

用于保存设备维修履历。

关键字段：

```text
id
device_id
task_id
diagnosis_trace_id
qa_trace_id
fault_type
alarm_code
fault_description
root_cause
repair_action
replaced_parts
verification_result
is_recurrent
completed_by
completed_at
created_at
updated_at
```

### 16.3 knowledge_contributions

用于一线经验投稿。

关键字段：

```text
id
title
content
contribution_type
manufacturer
product_series
device_type
device_id
submitted_by
review_status
created_at
updated_at
```

### 16.4 knowledge_review_records

用于审核记录。

关键字段：

```text
id
contribution_id
reviewer_id
review_action
review_comment
reviewed_at
created_at
```

### 16.5 model_output_corrections

用于模型输出修正。

关键字段：

```text
id
source_type
source_trace_id
original_output
corrected_output
correction_reason
submitted_by
review_status
approved_by
approved_at
created_at
updated_at
```

### 16.6 sop_templates

用于 SOP 模板。

关键字段：

```text
id
title
manufacturer
product_series
device_type
fault_type
maintenance_level
steps
safety_requirements
tools_required
materials_required
compliance_notes
status
created_at
updated_at
```

### 16.7 sop_execution_records

用于 SOP 执行记录。

关键字段：

```text
id
task_id
template_id
executor_id
step_results
abnormal_notes
status
started_at
completed_at
created_at
updated_at
```

---

## 17. 接口分组总表

### 17.1 Auth

```http
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
```

### 17.2 Users

```http
GET /api/users
POST /api/users
PATCH /api/users/{user_id}
PATCH /api/users/{user_id}/status
PATCH /api/users/{user_id}/role
```

### 17.3 Devices

```http
POST /api/devices
GET /api/devices
GET /api/devices/{device_id}
PATCH /api/devices/{device_id}
GET /api/devices/{device_id}/history
```

### 17.4 Knowledge

```http
POST /api/knowledge/documents/upload
GET /api/knowledge/documents
GET /api/knowledge/documents/{document_id}
GET /api/knowledge/documents/{document_id}/chunks
POST /api/knowledge/contributions
GET /api/knowledge/contributions
POST /api/knowledge/reviews/{contribution_id}/approve
POST /api/knowledge/reviews/{contribution_id}/reject
```

### 17.5 Media

```http
POST /api/media/upload
GET /api/media/{media_id}
DELETE /api/media/{media_id}
```

### 17.6 Retrieval

```http
POST /api/retrieval/query
```

### 17.7 Diagnosis

```http
POST /api/diagnosis/analyze
```

### 17.8 SOP

```http
POST /api/sop/templates
GET /api/sop/templates
POST /api/sop/recommend
POST /api/sop/executions
PATCH /api/sop/executions/{execution_id}
```

### 17.9 Tasks

```http
POST /api/maintenance/tasks
GET /api/maintenance/tasks
GET /api/maintenance/tasks/{task_id}
POST /api/maintenance/tasks/{task_id}/start
POST /api/maintenance/tasks/{task_id}/cancel
POST /api/maintenance/tasks/{task_id}/complete
```

### 17.10 Records

```http
GET /api/retrieval/records
GET /api/diagnosis/records
GET /api/record-center/search
GET /api/record-center/records/{record_type}/{record_id}
```

### 17.11 Models

```http
GET /api/models/status
GET /api/models/providers
PATCH /api/models/default-provider
GET /api/models/call-logs
```

### 17.12 System

```http
GET /api/health
GET /api/system/info
GET /api/system/status
GET /api/system/dashboard
```

---

## 18. 第一版演示流程设计

推荐比赛演示流程：

```text
1. 登录系统，展示不同角色权限。
2. 进入工作台，展示系统定位和数据概览。
3. 新建或查看一台华为 SUN2000 逆变器设备。
4. 上传华为/阳光电源真实资料和故障图片。
5. 系统解析资料并生成知识切片。
6. 使用设备型号、告警码、故障描述进行多模态检索。
7. 调用本地小模型生成检修问答结果。
8. 展示 references 和 retrieved_chunks。
9. 发起故障诊断，系统展示历史相似维修记录。
10. 系统生成安全提示和推荐处理措施。
11. 根据诊断结果推荐 SOP 作业流程。
12. 创建检修任务。
13. 执行 SOP 步骤并上传现场图片。
14. 完成任务，生成设备维修履历。
15. 一线人员提交经验总结。
16. 专家审核后纳入知识库。
17. 专家修正一次模型输出，并沉淀为知识。
18. 记录追溯中心展示 trace_id 全链路。
19. 系统状态页展示数据库、本地模型和部署信息。
```

---

## 19. 开发阶段设计

建议后续开发阶段：

```text
Task 02A：数据库设计与新版需求一致性审查
Task 02B：数据库模型与 migration 增强
Task 03：PostgreSQL 真实连接与迁移验收
Task 04：用户登录与权限系统
Task 05：设备台账与维修履历
Task 06：多模态知识库上传与解析
Task 07：本地/云端模型服务网关
Task 08：智能检索与大模型问答
Task 09：故障诊断与历史复发判断
Task 10：SOP 作业指引
Task 11：检修任务与维修记录
Task 12：知识投稿、审核与模型修正
Task 13：记录追溯中心
Task 14：前端页面整体联调
Task 15：LoongArch + Kylin 部署与演示验收
```

---

## 20. 验收设计

### 20.1 数据库验收

```text
1. 所有核心表存在。
2. 新增增强表存在。
3. 外键关系正确。
4. PostgreSQL migration 成功。
5. 无 SQLite fallback。
```

### 20.2 权限验收

```text
1. 不登录不能访问业务接口。
2. 不同角色权限不同。
3. viewer 不能执行写操作。
```

### 20.3 业务验收

```text
1. 设备台账可新建。
2. 维修履历可追溯。
3. 文档可上传并切片。
4. 图片可上传并关联。
5. 问答有真实 references。
6. 诊断有 safety_notes 和 related_history。
7. SOP 可推荐和执行。
8. 任务可完成并生成维修记录。
9. 投稿可审核。
10. 模型输出可修正。
```

### 20.4 部署验收

```text
1. 支持 LoongArch + Kylin 原生部署。
2. systemd 服务可配置。
3. Nginx 反向代理可配置。
4. PostgreSQL 原生服务可用。
5. 本地模型服务有接入说明。
```

---

## 21. 结论

本功能设计文档将 Energy-Maintenance 第一版明确为一个完整的多模态大模型检修作业辅助系统，而不是普通知识库问答工具。后续数据库、接口和前端开发必须围绕设备台账、维修履历、权限系统、多模态知识库、本地模型、故障诊断、SOP 作业指引、检修任务、知识审核和记录追溯形成真实闭环。
---

## Task 02A 功能设计补充确认

本节用于确认第一版本页面和后端模块边界。

### A. 前端页面清单

- LoginView：登录入口。
- DashboardView：系统概览。
- UserManagementView：用户、角色、状态管理。
- DeviceLedgerView：设备台账列表。
- DeviceDetailView：设备详情和历史检修记录。
- KnowledgeBaseView：知识文档上传、解析、切片和列表。
- KnowledgeReviewView：知识贡献和审核。
- RetrievalChatView：可追溯检修问答。
- FaultDiagnosisView：故障诊断和安全建议。
- SOPGuideView：SOP 作业指引。
- MaintenanceTaskView：检修任务列表和创建。
- TaskDetailView：任务详情、状态流转和处理记录。
- RecordCenterView：QA、诊断、任务和操作追溯。
- ModelServiceView：模型服务配置、健康状态和调用日志。
- SystemStatusView：系统状态、数据库状态、知识库统计。

### B. 后端模块清单

- auth。
- users。
- devices。
- knowledge。
- media。
- retrieval。
- diagnosis。
- sop。
- tasks。
- records。
- reviews。
- model_gateway。
- system。

### C. 设计一致性要求

前端页面、后端模块、数据库表和 API 合同应围绕同一组领域字段设计：manufacturer、product_series、model、device_type、fault_type、alarm_code、references、retrieved_chunks、trace_id、source_trace_id。
## Task 22A Agent Runtime Functional Addendum

The Agent Runtime foundation introduces a traceable orchestration layer for future multi-agent maintenance workflows.

Current functional boundary:

- Store agent definitions.
- Store tool registry metadata.
- Create rule-based demo / dry-run agent runs.
- Record steps, tool calls, approvals, artifacts, and event logs.
- Require human approval for high-risk or approval-marked tools.
- Preserve RBAC boundaries.

Deferred capabilities:

- Real `mimo-2.5` integration.
- Real multimodal inference.
- Direct business service tool execution.
- Agent Workbench UI.
- Embedding / pgvector.
- External graph database.

Future tasks must connect agent tools through existing service-layer modules rather than directly through repositories or SQLAlchemy models.
# Task 22B Agent Tool Functional Boundary

The agent runtime can orchestrate registered business tools over the existing Huawei/Sungrow PV inverter maintenance modules: knowledge retrieval, knowledge graph business context, device lookup, device history, media metadata lookup, OCR text lookup or blocked status, blocked mimo-2.5 placeholder, rule-based diagnosis, SOP generation, task draft creation, knowledge contribution draft creation, record-center lookup, safety guard, rule-based model gateway chat, correction draft creation, and human approval placeholder.

The runtime records every tool step and tool call. It does not finalize high-risk write actions; it creates draft artifacts and waits for human approval.

This remains a first-version service orchestration layer, not a real autonomous external-model agent.

---

## Task 22C External API Provider Gateway Functional Boundary

The External API Provider Gateway is a reserved integration layer for future multi-agent external API access. It provides provider definitions, tool-to-provider routes, dry-run checks, sanitized call logs, and health check records.

In Task 22C, the gateway does not perform real mimo-2.5, cloud model, local llama.cpp, or OCR calls. Agent tools can read route status and return blocked/dry-run results while preserving traceability.

Future integration only requires explicit configuration through environment variables and adapter completion. The database must never store real API keys.

## Task 22D Multimodal Evidence Center Functional Boundary

The multimodal evidence center stores media-side processing state and auxiliary evidence:

- media processing jobs
- OCR result records
- AI analysis records
- evidence links
- media multimodal summary

The center is connected to the External API Provider Gateway for provider route status and dry-run/blocked logging.

In Task 22D, real OCR and mimo-2.5 analysis are not executed. Machine outputs, when present from manual or future providers, are auxiliary evidence and require human review before being used in maintenance decisions.
## Task 22E Functional Addendum

The multimodal capability is now represented by a provider-adapter contract rather than direct external API calls in business services.

Functional behavior:

- External provider routing remains centralized in `ExternalApiGateway`.
- Adapter implementations construct sanitized request summaries for mimo-2.5, OpenAI-compatible vision/text, and OCR HTTP providers.
- Mock-run is available only for local workflow verification and persists explicitly mocked OCR or AI-analysis evidence.
- Agent tools read unified evidence-center results instead of directly coupling to provider-specific request formats.

The system still does not claim real cloud vision, real mimo-2.5, or real OCR recognition.

## Task 22F Functional Design Update

The first-version frontend now includes a 多模态证据中心 page.

The page acts as the operational entry for media-based evidence around PV inverter maintenance:

- media evidence selection;
- provider status visibility;
- processing-job lifecycle visibility;
- OCR and AI analysis result review;
- evidence links to diagnosis, retrieval, maintenance, record-center, and Agent Run sources;
- Agent workbench entry for dry-run tool orchestration.

All actions are backed by PostgreSQL-persisted backend APIs. The page does not perform real image fault recognition unless a later provider-integration task enables and validates real external calls.
## Task 22G Addendum: Multimodal Evidence Agent

The multimodal evidence agent coordinates media metadata, OCR evidence, visual analysis evidence, and safety review for Huawei/Sungrow PV inverter maintenance scenarios.

The agent does not directly call external APIs. It uses registered tools and Provider Gateway dry-run/mock-run contracts. When providers are not configured, OCR and visual analysis return blocked status. Mock-run results are explicitly marked and require human review.

Functional outputs:

- multimodal evidence summary artifact;
- safety checklist artifact;
- evidence trace summary artifact;
- media evidence links from media to agent run and generated artifacts;
- final answer explaining succeeded tools, blocked tools, mocked outputs, review requirements, and next steps.

## Task 22H Addendum: Diagnosis, SOP, and Task Agent Orchestration

Task 22H extends the Agent Runtime from evidence gathering into maintenance-assistance orchestration for Huawei/Sungrow PV inverter scenarios.

New dedicated agent flows:

- `fault_diagnosis_agent`: validates diagnosis context, loads device/history/media evidence, retrieves approved knowledge, queries graph context, runs rule-based diagnosis, runs the safety guard, and generates `diagnosis_summary`, `safety_checklist`, and `evidence_trace_summary` artifacts.
- `sop_planner_agent`: loads device and diagnosis context, retrieves SOP-related knowledge, queries graph context, generates an SOP draft, creates a safety checklist, and creates a pending `sop_draft_review` approval.
- `task_orchestration_agent`: loads device and history context, generates a maintenance task draft, creates a safety checklist, and creates a pending `task_draft_review` approval.

Functional boundaries:

- Diagnosis output is an assisted recommendation, not the final repair conclusion.
- SOP output is a draft artifact, not an executed SOP.
- Task output is a draft artifact, not a formal maintenance task.
- Approval changes only the agent approval record in this task.
- No real external API, OCR, embedding, pgvector, Neo4j, Docker, or SQLite capability is introduced.

## Task 22I Addendum: Knowledge Curator Agent

Task 22I adds `knowledge_curator_agent` as a draft-only knowledge curation workflow for Huawei/Sungrow PV inverter maintenance experience.

The agent consumes:

- engineer notes and fault symptoms;
- device context and recent maintenance history;
- source agent runs and artifacts from diagnosis, SOP, task, or multimodal evidence workflows;
- media evidence metadata;
- existing approved knowledge search results;
- knowledge graph business context;
- safety guard output.

Functional outputs:

- `maintenance_case_summary`: structured maintenance case summary;
- `knowledge_contribution_draft`: draft contribution for expert review;
- `kg_candidate_suggestion`: candidate concept/relation suggestions for a future graph update;
- `safety_checklist`: safety items for expert review;
- `evidence_trace_summary`: traceability summary linking source runs, artifacts, media, knowledge references, graph context, and approval state.

The workflow creates a pending approval:

- `approval_type=knowledge_contribution_draft_review`
- `requested_action=review_knowledge_contribution_draft`

Functional boundaries:

- Generated knowledge remains an Agent Artifact, not a formal knowledge contribution.
- Approval only updates the Agent Approval record.
- The agent does not create formal `knowledge_contributions`.
- The agent does not create formal `knowledge_documents` or `knowledge_chunks`.
- The agent does not create formal knowledge-graph nodes or edges.
- Formal conversion from an approved draft is handled by Task 22J.
- No real external API, OCR, embedding, pgvector, Neo4j, Docker, or SQLite capability is introduced.

## Task 22J Addendum: Approved Draft Conversion

Task 22J adds an explicit service layer for converting approved Agent draft artifacts into formal business objects.

Functional flow:

```text
Agent Artifact
  -> matching Agent Approval approved
  -> expert/admin explicit conversion request
  -> formal business object creation
  -> agent_event_logs conversion audit event
```

Supported conversions:

- `knowledge_contribution_draft` becomes a pending-review `knowledge_contributions` record.
- `sop_draft` becomes a draft `sop_templates` record.
- `task_draft` becomes a pending `maintenance_tasks` record.
- `kg_candidate_suggestion` becomes pending `kg_candidates` under a `kg_extraction_runs` record.

Safety boundaries:

- approval alone never creates formal objects;
- rejected, cancelled, missing, or non-approved approvals cannot be converted;
- duplicate conversion of the same artifact to the same target type is blocked;
- `viewer` and `engineer` users cannot convert artifacts;
- mocked or unreviewed AI evidence requires admin override;
- conversion does not create knowledge documents, knowledge chunks, SOP execution records, completed maintenance records, formal KG nodes, or formal KG edges.

This task does not introduce real external API calls, OCR, embedding, pgvector, Neo4j, Docker, SQLite, or delivery package generation.
## Task 24B Addendum: DashVector-Based Hybrid RAG

The selected Task 24B design uses PostgreSQL for business facts and DashVector for vector recall. PostgreSQL stores document, chunk, review, QA, KG, agent, and vector-index metadata; DashVector stores vector index data. Retrieval combines keyword candidates with vector candidates and then revalidates every vector hit against PostgreSQL approved / parsed / active state.

This design does not introduce pgvector, local vector columns, or an independent local vector database.

## Task 24D Addendum: Security and Secret Governance

The functional baseline now includes production startup validation, sanitized system status, secret-leak scanning, log sanitization, upload/path traversal verification, request body limits, lightweight rate limiting, and RBAC matrix acceptance.

Security behavior is intentionally conservative:

- real provider keys are accepted only from environment configuration and are never returned to frontend responses;
- external-provider, vector, model, OCR, and multimodal logs store sanitized summaries only;
- large JSON requests and oversized uploads are rejected before business processing;
- viewer users remain read-only;
- real DashVector / MIMO / OCR / Cloud LLM calls remain blocked unless explicitly configured and separately accepted.

## Task 24E Addendum: Agent Draft Conversion Audit

Agent-generated drafts can be converted into formal business objects only after human approval. Conversion now has a dedicated audit table, conversion trace id, status lifecycle, target object pointer, source artifact snapshot, and failure recording.

The conversion lifecycle is independent from approval. Approval does not automatically create formal objects. Duplicate and concurrent conversion requests for the same artifact and target are prevented by database constraint and service-level locking.
