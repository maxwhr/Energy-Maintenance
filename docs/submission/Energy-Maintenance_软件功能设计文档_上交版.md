# Energy-Maintenance 软件功能设计文档

**项目名称：** Energy-Maintenance  
**系统定位：** 光伏逆变器检修知识检索与作业辅助系统  
**文档版本：** v1.0  

---

## 1. 总体设计

Energy-Maintenance 采用 B/S 架构，前端提供设备台账、知识库、检修问答、故障诊断、SOP、任务和记录追溯界面；后端提供统一 API、业务服务、数据库访问和模型服务网关；数据库采用 PostgreSQL。

系统正式部署面向 LoongArch + Kylin 原生环境，使用 Python virtual environment、native PostgreSQL、Nginx 和 systemd。

---

## 2. 技术架构

### 2.1 前端技术

- Vue 3。
- Vite。
- TypeScript。
- Vue Router。
- Pinia。
- Axios。
- Element Plus。

### 2.2 后端技术

- FastAPI。
- Uvicorn。
- Pydantic。
- SQLAlchemy 2.x。
- Alembic。
- PostgreSQL。
- pypdf。
- python-docx。

### 2.3 模型服务架构

系统设置 Model Gateway 作为统一模型服务入口。业务模块只调用 Model Gateway，不直接绑定具体模型运行时。

本地模型路线采用 llama.cpp + GGUF；云端模型路线采用 OpenAI-compatible API，可对接兼容的 Qwen、DeepSeek 服务。

---

## 3. 后端分层设计

后端采用分层结构：

```text
api -> service -> repository -> model
```

API 层负责请求校验和统一响应；Service 层负责业务编排和事务边界；Repository 层负责数据库查询和写入；Model 层负责 SQLAlchemy 表结构定义。

---

## 4. 后端模块设计

| 模块 | 设计说明 |
| --- | --- |
| auth | 登录、会话、当前用户 |
| users | 用户、角色、状态管理 |
| devices | 光伏逆变器设备台账和设备详情 |
| knowledge | 文档上传、解析、切片、审核状态 |
| media | 故障图片和附件上传记录 |
| retrieval | PostgreSQL 关键词检索、来源追溯、问答记录 |
| diagnosis | 故障诊断、告警码查询、诊断记录 |
| sop | SOP 模板和执行记录 |
| tasks | 检修任务创建、查询、状态更新 |
| records | QA、诊断、任务、日志追溯 |
| reviews | 知识审核、模型输出纠错 |
| model_gateway | 模型服务配置、调用和日志记录 |
| system | 健康检查、数据库状态、知识库统计 |

---

## 5. 前端页面设计

| 页面 | 主要功能 |
| --- | --- |
| LoginView | 用户登录入口 |
| DashboardView | 系统概览、核心指标、快捷入口 |
| UserManagementView | 用户列表、角色、启停状态 |
| DeviceLedgerView | 设备台账列表、筛选、创建入口 |
| DeviceDetailView | 设备基本信息、历史检修记录、关联任务 |
| KnowledgeBaseView | 文档上传、解析结果、知识切片查看 |
| KnowledgeReviewView | 知识贡献、审核、驳回和发布 |
| RetrievalChatView | 检修问答、来源引用、切片查看 |
| FaultDiagnosisView | 故障诊断、排查步骤、安全注意事项 |
| SOPGuideView | SOP 模板选择、步骤执行、风险提示 |
| MaintenanceTaskView | 任务列表、创建任务、状态筛选 |
| TaskDetailView | 任务详情、状态流转、处理结果 |
| RecordCenterView | 问答、诊断、任务、操作追溯 |
| ModelServiceView | 模型服务配置、健康状态、调用日志 |
| SystemStatusView | 后端状态、数据库状态、知识库统计 |

---

## 6. 核心业务流程

### 6.1 知识入库流程

```text
上传文档
-> 保存上传文件
-> 解析文本
-> 文本清洗
-> 文本切片
-> 写入 knowledge_documents
-> 写入 knowledge_chunks
-> 更新解析状态和切片数量
```

### 6.2 检修问答流程

```text
用户输入问题
-> 解析厂家、型号、设备类型、告警码等条件
-> PostgreSQL 结构化过滤和关键词检索
-> 读取真实 knowledge_chunks
-> 生成结构化回答
-> 返回 references 和 retrieved_chunks
-> 写入 qa_records
```

### 6.3 故障诊断流程

```text
输入故障现象、告警信息、设备状态和图片描述
-> 匹配故障类型和设备历史
-> 生成可能原因、排查步骤、安全注意事项、推荐措施
-> 返回可追溯结果
-> 写入 diagnosis_records
```

### 6.4 SOP 执行流程

```text
选择设备和故障类型
-> 匹配 SOP 模板
-> 展示步骤和安全提示
-> 记录执行状态
-> 关联检修任务和执行结果
```

---

## 7. 数据模型设计

系统核心表包括：

- users。
- devices。
- uploaded_media。
- device_maintenance_records。
- knowledge_documents。
- knowledge_chunks。
- knowledge_contributions。
- knowledge_review_records。
- model_output_corrections。
- qa_records。
- diagnosis_records。
- maintenance_tasks。
- sop_templates。
- sop_execution_records。
- operation_logs。
- model_call_logs。

关键字段包括 manufacturer、product_series、model、device_type、document_type、fault_type、alarm_code、trace_id、references、retrieved_chunks、source_trace_id。

---

## 8. API 设计

系统 API 统一使用 `/api` 前缀，响应结构统一为：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

核心 API 分类：

- `/api/health` 和 `/api/system/*`：系统状态。
- `/api/auth/*`：认证。
- `/api/users/*`：用户管理。
- `/api/devices/*`：设备台账。
- `/api/knowledge/*`：知识库。
- `/api/media/*`：媒体上传。
- `/api/retrieval/query`：检修问答。
- `/api/diagnosis/*`：故障诊断。
- `/api/sop/*`：SOP。
- `/api/maintenance/tasks/*`：检修任务。
- `/api/records/*`：记录追溯。
- `/api/model-gateway/*`：模型服务。

---

## 9. 检索与回答设计

第一版检索采用 PostgreSQL 结构化过滤和关键词评分，重点支持：

- 厂家过滤。
- 产品系列过滤。
- 设备型号匹配。
- 告警码精确匹配。
- 文档类型过滤。
- 知识切片关键词检索。
- 设备历史检修记录匹配。

回答结果包含 answer、suggested_steps、references、retrieved_chunks、confidence、trace_id。references 必须来自真实知识库或业务记录。

---

## 10. 多模态设计

第一版多模态输入包括文本、设备型号、告警码、故障图片和图片描述。图片上传后保存到媒体表，并可关联设备、诊断记录和检修任务。

OCR 通过 OCRService 抽象预留，具体引擎在目标环境验证后接入。

---

## 11. 部署设计

系统正式部署采用：

- LoongArch + Kylin。
- Python virtual environment。
- native PostgreSQL。
- systemd 管理后端服务。
- Nginx 提供前端静态资源和反向代理。

---

## 12. 验收设计

系统验收应覆盖：

1. PostgreSQL 连接和 Alembic migration。
2. 华为、阳光电源样例文档上传和知识切片生成。
3. 检修问答返回真实 references 并写入 qa_records。
4. 故障诊断返回安全注意事项并写入 diagnosis_records。
5. 检修任务创建、查询和状态更新。
6. 记录中心可按 trace_id 追溯。
7. 前端构建成功，主要页面可以完成核心操作。
8. LoongArch + Kylin 部署说明和服务配置可执行。
