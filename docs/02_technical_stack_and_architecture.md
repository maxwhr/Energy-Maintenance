# Energy-Maintenance 技术栈与系统架构设计文档

> 文件命名：`docs/02_technical_stack_and_architecture.md`  
> 文档版本：v1.0  
> 项目名称：Energy-Maintenance  
> 第一版业务范围：面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统  
> 适用对象：产品设计、系统架构、后端开发、前端开发、数据库设计、部署实施、Codex/vibe coding 开发约束

---

## 1. 文档目的

本文档用于明确 Energy-Maintenance 项目的技术栈、系统架构、模块划分、开发约束与部署路线，作为后续 vibe coding 的技术基线。

本项目不是“先做一个粗糙雏形，再不断返工”的开发方式，而是尽量通过完整、清晰、可执行的前期设计，让后续 AI 编码能够直接接近最终可交付标准。

因此，本文档不只描述“使用什么技术”，还要明确：

1. 为什么选择该技术；
2. 每项技术在系统中的职责边界；
3. 后端、前端、数据库、知识库、检索问答、部署之间如何协作；
4. Codex 在开发时应该遵守哪些架构规则；
5. 哪些内容第一版必须完成，哪些内容只预留，不应提前扩散。

---

## 2. 项目技术定位

Energy-Maintenance 第一版定位为：

> 面向华为 Huawei / SUN2000 / FusionSolar 体系与阳光电源 Sungrow / SG 系列光伏逆变器的检修知识检索与作业辅助系统。

系统核心能力包括：

1. 光伏逆变器检修资料上传、解析、切片与入库；
2. 基于知识切片的检修知识问答；
3. 逆变器故障现象与告警信息的辅助诊断；
4. 检修任务创建、状态管理和结果记录；
5. 问答记录、诊断记录、检修任务的可追溯管理；
6. 后续可扩展 pgvector、embedding、大模型和 OCR，但第一版不强制实现。

系统第一版不做泛化场景，不扩展到储能电池系统、箱式变压器、电力巡检设备、通用新能源设备或车辆维修。

---

## 3. 总体技术路线

### 3.1 总体架构模式

项目采用：

```text
Vue3 前端管理系统
        ↓ HTTP / JSON API
FastAPI 后端服务
        ↓
Service 业务层
        ↓
Repository 数据访问层
        ↓
PostgreSQL 数据库
        ↓
knowledge_documents / knowledge_chunks / qa_records / diagnosis_records / maintenance_tasks
```

核心架构是前后端分离：

```text
frontend/    Vue3 + Vite + TypeScript + Element Plus
backend/     FastAPI + SQLAlchemy + Alembic + PostgreSQL
docs/        产品需求、架构、数据库、接口、页面、知识库、检索、部署、验收文档
deploy/      后续存放 systemd、Nginx、Kylin/LoongArch 原生部署配置
storage/     后端文件上传、样例资料、解析缓存等运行时目录
```

### 3.2 第一版架构目标

第一版架构必须支持以下闭环：

```text
上传华为/阳光电源逆变器资料
        ↓
解析 txt / md / pdf / docx 文本
        ↓
文本清洗与知识切片
        ↓
写入 PostgreSQL
        ↓
用户输入逆变器检修问题
        ↓
检索 knowledge_chunks
        ↓
返回 answer + references + retrieved_chunks
        ↓
保存 qa_records
        ↓
可生成检修任务并追溯记录
```

第一版架构不追求复杂模型能力，而追求：

1. 业务场景聚焦；
2. 数据结构稳定；
3. 接口契约稳定；
4. 知识来源可追溯；
5. 检索问答真实基于数据库；
6. 后续增强能力有清晰扩展点。

---

## 4. 技术栈总览

### 4.1 后端技术栈

| 类别 | 技术 | 用途 |
|---|---|---|
| 语言 | Python 3.10+ | 后端开发语言 |
| Web 框架 | FastAPI | API 服务、OpenAPI 文档、请求校验 |
| ASGI 服务 | Uvicorn | 本地开发与生产服务启动 |
| 数据建模 | SQLAlchemy 2.x | ORM、数据库模型、Repository 数据访问 |
| 数据迁移 | Alembic | 数据库 schema 版本管理 |
| 数据库 | PostgreSQL | 核心关系型数据库 |
| 配置管理 | pydantic-settings / python-dotenv | `.env` 配置读取 |
| 请求模型 | Pydantic | API 请求与响应 schema |
| 文件上传 | python-multipart | multipart/form-data 文件上传 |
| PDF 解析 | pypdf | 文本型 PDF 解析，优先兼容 LoongArch |
| Word 解析 | python-docx | docx 文档解析 |
| 测试 | pytest，可后续补充 | 单元测试与接口测试 |
| 代码检查 | ruff，可后续统一 | 代码风格与静态检查 |

第一版后端不强制接入：

```text
真实大模型
真实 embedding
pgvector
OCR
Celery / RQ 异步任务队列
Redis
复杂权限系统
```

这些能力后续可在架构预留点上逐步增强。

### 4.2 前端技术栈

| 类别 | 技术 | 用途 |
|---|---|---|
| 框架 | Vue 3 | 前端页面开发 |
| 构建工具 | Vite | 前端开发、构建 |
| 语言 | TypeScript | 类型约束，提高可维护性 |
| UI 组件库 | Element Plus | 管理系统页面组件 |
| 路由 | Vue Router | 页面路由 |
| 状态管理 | Pinia | 全局状态管理 |
| HTTP 客户端 | Axios | 调用 FastAPI 接口 |
| 样式 | CSS / Element Plus theme | 工业化、管理平台风格 |

第一版前端不追求复杂动画，不做移动端优先适配，不做炫技式 UI。页面应服务于检修业务流程。

### 4.3 数据库技术栈

数据库正式确定为：

```text
PostgreSQL
```

访问方式：

```text
SQLAlchemy 2.x ORM
Alembic migration
```

数据库连接必须通过 `.env` 中的 `DATABASE_URL` 配置，不允许在代码中写死数据库地址、用户名、密码或端口。

### 4.4 部署技术栈

最终部署环境：

```text
LoongArch + Kylin
```

最终部署方式：

```text
Python virtual environment
PostgreSQL native service
systemd backend service
Nginx frontend static hosting
Nginx reverse proxy for FastAPI
```

明确不采用 Docker 作为 Energy-Maintenance 的正式部署路线。

---

## 5. 技术选型原则

### 5.1 为什么选择 FastAPI

FastAPI 适合本项目的原因：

1. 原生支持 OpenAPI，方便比赛展示接口能力；
2. Pydantic 校验清晰，适合严格定义请求与响应；
3. 与 Python 文档解析、RAG、模型服务生态兼容；
4. 开发效率高，适合 vibe coding；
5. 部署方式简单，适合 LoongArch + Kylin 原生部署。

约束：

1. API 文件只负责请求处理和响应返回；
2. 不允许把数据库操作、检索逻辑、文档解析逻辑堆在 API 函数里；
3. 所有业务逻辑必须下沉到 service、repository、rag、knowledge 等模块。

### 5.2 为什么选择 Vue3 + Element Plus

Vue3 + Element Plus 适合做工业运维管理平台：

1. 表单、表格、抽屉、弹窗、标签等组件成熟；
2. 页面开发效率高；
3. 适合展示知识库、任务列表、记录追溯等管理型页面；
4. 与 Vite + TypeScript 组合稳定。

约束：

1. 页面不能做成普通聊天软件；
2. 页面文案必须围绕华为/阳光电源光伏逆变器检修；
3. 页面下拉选项不能泛化到大量无关设备；
4. API 调用必须统一封装在 `src/api/`，不要在页面中硬写多个重复 axios 调用。

### 5.3 为什么选择 PostgreSQL

PostgreSQL 适合本项目：

1. 关系型数据结构清晰，适合知识文档、切片、任务、记录管理；
2. 后续可扩展 pgvector，实现向量检索；
3. LoongArch + Kylin 原生部署可行；
4. 与 SQLAlchemy / Alembic 兼容成熟；
5. 支持 JSON / JSONB，适合保存 references、suggested_steps、诊断步骤等结构化内容。

约束：

1. 正式开发数据库不使用 SQLite；
2. 不允许绕过 Alembic 手动建表作为正式方案；
3. 所有 schema 变更必须通过 migration 管理；
4. 本地可以临时连接已有 PostgreSQL 实例，但不能把其他项目数据库作为正式依赖。

### 5.4 为什么第一版不立即接入大模型和 embedding

第一版先要保证：

```text
资料能入库
切片能检索
来源能追溯
记录能保存
```

如果在这个闭环未跑通前就接入 embedding、pgvector、大模型，会导致问题定位困难：

1. 检索不到结果时，不知道是上传失败、切片失败、embedding 失败还是检索失败；
2. 大模型可能掩盖知识库检索质量问题；
3. Codex 容易为了“功能完整”写出大量未验证逻辑；
4. 后续在 LoongArch 上部署复杂依赖风险更高。

因此第一版采用：

```text
关键词检索 + 规则型回答生成 + references 追溯
```

后续再逐步增强为：

```text
关键词检索 → pgvector 向量检索 → 混合检索 → rerank → 大模型生成
```

---

## 6. 后端架构设计

### 6.1 后端目录结构

后端推荐结构如下：

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── router.py
│   │   └── v1/
│   │       ├── health.py
│   │       ├── system.py
│   │       ├── knowledge.py
│   │       ├── retrieval.py
│   │       ├── maintenance.py
│   │       └── records.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── exceptions.py
│   │   └── response.py
│   ├── models/
│   │   ├── user.py
│   │   ├── device.py
│   │   ├── knowledge.py
│   │   ├── maintenance.py
│   │   └── record.py
│   ├── schemas/
│   │   ├── knowledge.py
│   │   ├── retrieval.py
│   │   ├── maintenance.py
│   │   ├── record.py
│   │   ├── system.py
│   │   └── health.py
│   ├── repositories/
│   │   ├── knowledge_repository.py
│   │   ├── maintenance_repository.py
│   │   ├── record_repository.py
│   │   ├── device_repository.py
│   │   └── user_repository.py
│   ├── services/
│   │   ├── knowledge_service.py
│   │   ├── retrieval_service.py
│   │   ├── maintenance_service.py
│   │   └── record_service.py
│   ├── knowledge/
│   │   ├── file_storage.py
│   │   ├── document_parser.py
│   │   ├── text_cleaner.py
│   │   ├── text_splitter.py
│   │   └── document_processor.py
│   ├── rag/
│   │   ├── retriever.py
│   │   ├── prompt_builder.py
│   │   └── qa_service.py
│   ├── maintenance/
│   │   └── workflow.py
│   ├── multimodal/
│   │   └── multimodal_service.py
│   └── ocr/
│       └── ocr_service.py
├── alembic/
├── storage/
├── tests/
├── pyproject.toml
├── alembic.ini
├── .env.example
└── README.md
```

### 6.2 后端分层职责

#### 6.2.1 API 层

位置：

```text
backend/app/api/routes/
```

职责：

1. 接收 HTTP 请求；
2. 调用 Pydantic schema 校验请求；
3. 调用 service 层；
4. 返回统一响应结构；
5. 把业务异常转成 HTTP 错误或统一错误响应。

API 层不允许：

1. 直接写 SQL；
2. 直接操作 SQLAlchemy model；
3. 直接解析上传文件；
4. 直接构造检索算法；
5. 直接写复杂业务逻辑；
6. 直接保存记录。

#### 6.2.2 Schema 层

位置：

```text
backend/app/schemas/
```

职责：

1. 定义请求体；
2. 定义响应体；
3. 定义列表分页结构；
4. 定义枚举字段；
5. 定义前后端契约。

Schema 必须服务于接口契约，不能随意改字段名。

重要 schema 包括：

```text
KnowledgeDocumentCreate
KnowledgeDocumentRead
KnowledgeChunkRead
RetrievalQueryRequest
RetrievalQueryResponse
DiagnosisRequest
DiagnosisResponse
MaintenanceTaskCreate
MaintenanceTaskRead
QARecordRead
DiagnosisRecordRead
PageResponse
```

#### 6.2.3 Model 层

位置：

```text
backend/app/models/
```

职责：

1. 定义 SQLAlchemy 数据模型；
2. 定义表名；
3. 定义字段类型、约束、默认值；
4. 定义外键关系；
5. 作为 Alembic metadata 来源。

Model 层不能包含业务流程逻辑。

#### 6.2.4 Repository 层

位置：

```text
backend/app/repositories/
```

职责：

1. 封装数据库增删改查；
2. 提供分页查询；
3. 提供过滤查询；
4. 提供复杂检索查询的数据库候选集；
5. 保持 API 和 service 不直接依赖 SQL 细节。

Repository 层可以使用 SQLAlchemy 查询，但不处理业务策略。

#### 6.2.5 Service 层

位置：

```text
backend/app/services/
```

职责：

1. 组织业务流程；
2. 调用 repository；
3. 调用 knowledge、rag、maintenance 子模块；
4. 控制事务边界；
5. 处理状态流转；
6. 生成 trace_id；
7. 保存问答、诊断和任务记录。

Service 层是后端业务主入口。

#### 6.2.6 Knowledge 层

位置：

```text
backend/app/knowledge/
```

职责：

1. 文件保存；
2. 扩展名和大小校验；
3. 文档解析；
4. 文本清洗；
5. 文本切片；
6. 组织文档处理流程。

Knowledge 层不直接处理 HTTP 请求，不直接向前端返回响应。

#### 6.2.7 RAG 层

位置：

```text
backend/app/rag/
```

职责：

1. 检索知识切片；
2. 构造检修问答上下文；
3. 生成规则型回答；
4. 后续扩展 embedding、pgvector、大模型调用；
5. 确保 references 来自真实 knowledge_chunks。

第一版 RAG 实际上是“轻量检索问答层”，后续再升级为完整 RAG。

#### 6.2.8 Maintenance 层

位置：

```text
backend/app/maintenance/
```

职责：

1. 定义逆变器检修工作流；
2. 定义故障类型到排查步骤的基础规则；
3. 生成检修任务建议；
4. 后续支持 SOP 生成和报告导出。

---

## 7. 前端架构设计

### 7.1 前端目录结构

```text
frontend/
├── src/
│   ├── api/
│   │   ├── request.ts
│   │   ├── system.ts
│   │   ├── knowledge.ts
│   │   ├── retrieval.ts
│   │   ├── maintenance.ts
│   │   └── records.ts
│   ├── assets/
│   │   └── styles.css
│   ├── components/
│   ├── layouts/
│   │   └── MainLayout.vue
│   ├── router/
│   │   └── index.ts
│   ├── stores/
│   │   └── app.ts
│   ├── views/
│   │   ├── DashboardView.vue
│   │   ├── KnowledgeBaseView.vue
│   │   ├── RetrievalChatView.vue
│   │   ├── FaultDiagnosisView.vue
│   │   ├── MaintenanceTaskView.vue
│   │   ├── RecordCenterView.vue
│   │   └── SystemStatusView.vue
│   ├── App.vue
│   └── main.ts
├── package.json
├── vite.config.ts
├── tsconfig.json
└── README.md
```

### 7.2 前端页面职责

| 页面 | 职责 |
|---|---|
| DashboardView | 展示系统定位、核心统计、快捷入口 |
| KnowledgeBaseView | 上传华为/阳光逆变器资料，查看文档和切片 |
| RetrievalChatView | 检修知识问答，展示 answer、references、retrieved_chunks |
| FaultDiagnosisView | 输入告警/故障现象，输出诊断建议 |
| MaintenanceTaskView | 创建、查看、更新检修任务 |
| RecordCenterView | 查看问答记录、诊断记录、任务记录 |
| SystemStatusView | 查看后端、数据库、知识库统计与系统版本 |

### 7.3 前端 API 调用规则

1. 所有 API 调用必须封装在 `src/api/`；
2. 页面组件不直接写完整 URL；
3. `request.ts` 统一处理 baseURL、错误提示、响应解包；
4. 前端请求路径必须与后端对外路径一致；
5. 第一版 API 路径统一为 `/api/...`，不要在前端写公开版本化 API 前缀；
6. 接口返回结构统一处理：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 7.4 页面风格约束

页面风格应体现：

```text
国产光伏逆变器检修
工业运维
知识库管理
检修作业辅助
记录可追溯
```

避免：

```text
通用 AI 聊天页面
教育平台页面
客服机器人页面
泛新能源门户页面
过度花哨的数据大屏
```

---

## 8. 数据库架构设计

### 8.1 核心表

第一版核心表：

```text
users
devices
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

可后置表：

```text
operation_logs
model_call_logs
```

### 8.2 场景关键字段

由于项目第一版聚焦华为与阳光电源光伏逆变器，数据库字段必须支持厂家和产品系列：

```text
manufacturer: huawei / sungrow
product_series: SUN2000 / FusionSolar / SG
device_type: pv_inverter
document_type: manual / alarm_code / sop / fault_case / inspection_standard / maintenance_record
```

如果当前数据库尚未包含 `manufacturer` 和 `product_series`，应通过后续小任务和 Alembic migration 增加，不能在多个业务字段里临时拼接厂家信息。

### 8.3 数据库连接规则

`.env` 示例：

```env
APP_NAME=Energy-Maintenance
APP_ENV=development
APP_VERSION=0.1.0

DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:5432/energy_maintenance

BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_DOCUMENT_EXTENSIONS=txt,md,pdf,docx
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=150
```

禁止：

```text
在 Python 代码中写死数据库密码
在代码中写死 localhost
在代码中写死 Docker 网络主机名 postgres
使用 SQLite 作为正式开发数据库
跳过 Alembic 直接手动建表作为正式方案
```

### 8.4 Alembic 规则

1. 所有表结构变化必须产生 migration；
2. migration 文件必须与 SQLAlchemy model 保持一致；
3. 不允许删除已有 migration 链；
4. 不允许为了图省事重置数据库作为默认开发流程；
5. 迁移执行命令固定：

```bash
cd backend
alembic -c alembic.ini upgrade head
```

使用 uv 时：

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

---

## 9. 知识库架构设计

### 9.1 文档处理流程

```text
用户上传文档
        ↓
file_storage 保存原始文件
        ↓
document_parser 按文件类型提取文本
        ↓
text_cleaner 清洗文本
        ↓
text_splitter 生成知识切片
        ↓
KnowledgeService 保存 document 和 chunks
        ↓
更新 parse_status、chunk_count、parsed_at
```

### 9.2 支持文件类型

第一版支持：

```text
txt
md
pdf
docx
```

约束：

1. PDF 只支持文本型 PDF；
2. 扫描版 PDF OCR 不在第一版范围；
3. docx 解析段落和表格文本；
4. 文件解析失败必须保存错误原因；
5. 不支持的扩展名返回明确错误；
6. 空文件返回明确错误。

### 9.3 parse_status 状态

```text
pending
processing
parsed
failed
```

要求：

1. 解析成功：`parse_status = parsed`，`chunk_count > 0`；
2. 解析失败：`parse_status = failed`，写入 `error_message`；
3. 不允许出现文档状态 parsed 但 chunk_count 为 0 的成功状态；
4. 不允许 chunks 写入成功但文档状态仍为 processing。

### 9.4 切片原则

默认：

```text
chunk_size = 1000
chunk_overlap = 150
```

切片原则：

1. 尽量按段落边界切分；
2. 保留章节标题；
3. 保留告警码、型号、单位、参数；
4. 不过度清洗；
5. 不删除英文型号，例如 SUN2000、SG320HX；
6. 不删除厂家名称，例如 Huawei、Sungrow、华为、阳光电源。

---

## 10. 检索问答架构设计

### 10.1 第一版检索策略

第一版使用：

```text
PostgreSQL 文本字段查询 + 规则型关键词评分
```

检索范围：

```text
knowledge_chunks.content
knowledge_chunks.section_title
knowledge_documents.title
knowledge_documents.summary
knowledge_documents.manufacturer
knowledge_documents.product_series
knowledge_documents.document_type
knowledge_documents.device_type
```

过滤条件：

```text
parse_status = parsed
status = active
manufacturer，可选
product_series，可选
document_type，可选
device_type = pv_inverter
```

### 10.2 检索结果要求

每条 retrieved_chunk 至少包含：

```text
chunk_id
document_id
document_title
manufacturer
product_series
document_type
device_type
section_title
content
score
chunk_index
page_number
source
created_at
```

### 10.3 回答生成策略

第一版可以使用规则型回答生成，不接真实大模型。

要求：

1. answer 必须基于 retrieved_chunks 摘要生成；
2. references 必须来自真实 retrieved_chunks；
3. 不允许编造文档标题、页码、来源；
4. 无检索结果时，references 为空；
5. suggested_steps 至少包含安全确认、故障核对、状态检查、部件排查、处理确认、复检归档；
6. confidence 不得返回 1.0；
7. 每次问答必须保存 qa_records；
8. trace_id 必须可追溯。

### 10.4 后续增强路线

后续增强顺序：

```text
Task A：补充 manufacturer / product_series 字段
Task B：优化中文关键词检索
Task C：加入 PostgreSQL 全文检索，可选
Task D：加入 pgvector 字段和 migration
Task E：生成 embedding 并写入 knowledge_chunks
Task F：实现向量检索
Task G：实现关键词 + 向量混合检索
Task H：接入大模型回答生成
Task I：保留 references 强约束
```

不要跳过 A-F 直接接大模型。

---

## 11. 故障诊断架构设计

### 11.1 输入字段

故障诊断接口应逐步收敛为：

```text
manufacturer
product_series
device_type = pv_inverter
alarm_code
fault_type
fault_description
device_status
site_condition，可选
```

### 11.2 典型故障类型

第一版固定支持：

```text
low_insulation_resistance
dc_abnormal
ac_overvoltage
ac_undervoltage
grid_connection_fault
over_temperature
fan_fault
communication_interruption
device_offline
mppt_abnormal
low_power_generation
alarm_code_query
```

### 11.3 输出字段

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

### 11.4 诊断策略

第一版可以采用：

```text
规则型诊断 + 知识库检索 references
```

要求：

1. 诊断建议必须适配华为/阳光电源逆变器；
2. 不要生成泛泛的“检查设备是否正常”；
3. 对电气安全风险必须提示断电、绝缘、防护、资质要求；
4. 诊断结果必须保存到 diagnosis_records；
5. 后续可接入 RAG 和大模型增强。

---

## 12. 系统部署架构

### 12.1 本地开发环境

本地开发允许：

```text
Windows + Python venv/uv + Node + PostgreSQL
```

本地 PostgreSQL 可以是：

1. 当前 Windows 原生 PostgreSQL；
2. 其他本地可访问 PostgreSQL 实例；
3. 仅用于开发验证的已有数据库服务。

但必须注意：

```text
本地临时数据库不等于正式部署方案
Energy-Maintenance 不依赖其他项目数据库
Energy-Maintenance 不创建 Docker 部署文件
```

### 12.2 龙芯 / 麒麟正式部署

正式部署环境：

```text
LoongArch CPU
Kylin OS
PostgreSQL native service
Python virtual environment
systemd
Nginx
```

部署结构建议：

```text
/opt/energy-maintenance/
├── backend/
├── frontend-dist/
├── storage/
├── logs/
├── .env
└── scripts/
```

后端由 systemd 管理：

```text
energy-maintenance-backend.service
```

前端由 Nginx 托管，API 由 Nginx 反向代理。

### 12.3 部署约束

禁止：

```text
Dockerfile
docker-compose.yml
将 Docker 作为部署路线
依赖 x86-only 的本地模型组件
在服务器上使用开发数据库配置
```

优先：

```text
纯 Python 或兼容 LoongArch 的依赖
pypdf 而非优先 PyMuPDF
PostgreSQL 原生安装
systemd 管理后端服务
Nginx 统一入口
```

---

## 13. 配置管理规范

### 13.1 配置文件

后端配置：

```text
backend/.env
backend/.env.example
```

前端配置：

```text
frontend/.env.development，可选
frontend/.env.production，可选
```

### 13.2 配置项

必要后端配置：

```env
APP_NAME=Energy-Maintenance
APP_ENV=development
APP_VERSION=0.1.0

DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:5432/energy_maintenance

BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_DOCUMENT_EXTENSIONS=txt,md,pdf,docx
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=150
```

后续可增加：

```env
LLM_PROVIDER=
LLM_API_BASE=
LLM_API_KEY=
EMBEDDING_PROVIDER=
EMBEDDING_MODEL=
ENABLE_PGVECTOR=false
```

但第一版不要求启用。

### 13.3 配置原则

1. `.env.example` 可以提交；
2. `.env` 不应提交真实密码；
3. 所有环境差异通过 `.env` 解决；
4. 不允许在代码中使用固定数据库地址；
5. 不允许把 Docker 网络服务名写死到代码或默认配置中。

---

## 14. 统一响应与错误处理

### 14.1 统一成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

### 14.2 统一错误响应

```json
{
  "code": 400,
  "message": "Invalid request",
  "data": null
}
```

或：

```json
{
  "code": 500,
  "message": "Internal server error",
  "data": null
}
```

### 14.3 常见错误场景

必须明确处理：

1. 数据库不可连接；
2. 文件扩展名不支持；
3. 文件为空；
4. 文件大小超限；
5. 文档解析失败；
6. 文档不存在；
7. 文档未解析成功，不允许参与检索；
8. 检索问题为空；
9. top_k 超过限制；
10. 检修任务不存在；
11. 记录查询分页参数非法。

API 不应返回 Python traceback 给前端。

---

## 15. 日志与追溯架构

### 15.1 trace_id

以下操作必须生成或保留 trace_id：

```text
检索问答
故障诊断
后续大模型调用
后续文档解析任务
```

trace_id 用于定位：

1. 用户问题；
2. 检索到哪些 chunks；
3. 返回了哪些 references；
4. 保存了哪条 qa_record 或 diagnosis_record。

### 15.2 记录保存

必须保存：

```text
qa_records
diagnosis_records
maintenance_tasks
```

后续可增加：

```text
operation_logs
model_call_logs
```

### 15.3 日志文件

后续部署时建议：

```text
/opt/energy-maintenance/logs/backend.log
/opt/energy-maintenance/logs/error.log
```

第一版可以先使用标准输出，由 systemd 管理日志。

---

## 16. 测试与验收架构

### 16.1 不允许仅用静态检查替代真实验收

以下检查有价值，但不能等同于功能完成：

```text
python -m compileall
ruff check
npm run build
alembic upgrade head --sql
OpenAPI 能访问
```

真正功能完成必须有真实闭环：

```text
PostgreSQL 可连接
alembic upgrade head 成功
上传样例文档成功
knowledge_chunks 非空
retrieval/query 返回真实 references
qa_records 写入成功
前端能展示真实结果
```

### 16.2 第一版核心验收闭环

```text
1. 启动 PostgreSQL
2. 执行 alembic upgrade head
3. 上传华为或阳光逆变器样例资料
4. 确认 parse_status = parsed
5. 确认 chunk_count > 0
6. 查询 chunks，确认内容真实来自资料
7. 提问“逆变器告警后如何排查？”
8. references 不为空
9. retrieved_chunks 不为空
10. qa_records 写入成功
11. 前端展示 answer、references、trace_id、confidence
```

### 16.3 后续测试分层

建议逐步补充：

```text
unit tests：文本清洗、切片、关键词检索
repository tests：数据库增删改查
api tests：接口请求响应
e2e tests：上传-检索-记录闭环
deployment smoke tests：服务器部署冒烟测试
```

---

## 17. 代码质量约束

### 17.1 通用约束

1. 文件和目录使用英文命名；
2. 不使用拼音命名；
3. 不使用中文文件名；
4. 不写无意义注释；
5. 不把所有逻辑堆进单个文件；
6. 不大规模重构已稳定模块；
7. 不随意修改 API 路径；
8. 不删除历史 migration；
9. 不伪造验收结果。

### 17.2 后端代码约束

1. API 层只处理请求和响应；
2. Service 层处理业务流程；
3. Repository 层处理数据库；
4. Knowledge 层处理文件和文本；
5. RAG 层处理检索和问答；
6. 所有数据库 session 必须合理关闭；
7. 所有上传文件必须做安全检查；
8. 所有异常必须返回明确错误。

### 17.3 前端代码约束

1. API 请求统一封装；
2. 页面字段与后端 schema 对齐；
3. 下拉选项围绕华为、阳光电源、光伏逆变器；
4. 不写死模拟结果作为正式展示；
5. 加载、空数据、错误状态必须处理；
6. references 和 retrieved_chunks 必须清晰展示。

---

## 18. 后续能力演进路线

### 18.1 第一版必须完成

```text
PostgreSQL 持久化
文档上传解析切片
关键词检索
可追溯问答
故障诊断
检修任务
记录追溯
系统状态
```

### 18.2 第二阶段增强

```text
manufacturer / product_series 深度筛选
华为与阳光样例资料库完善
故障类型结构化
记录中心页面完善
诊断结果关联 references
```

### 18.3 第三阶段智能增强

```text
pgvector
embedding
混合检索
reranker
大模型回答生成
model_call_logs
```

### 18.4 第四阶段多模态增强

```text
告警截图 OCR
设备铭牌识别
扫描版 PDF OCR
图片辅助诊断
```

### 18.5 第五阶段交付增强

```text
LoongArch + Kylin 部署
systemd
Nginx
备份恢复
日志管理
验收脚本
答辩演示脚本
```

---

## 19. Codex / vibe coding 开发规则

后续给 Codex 的任务必须遵循小任务制。

### 19.1 禁止大而全提示词

不要再使用类似：

```text
完成第五阶段所有 embedding、pgvector、大模型、OCR、前端展示和部署优化
```

应拆成：

```text
只补 manufacturer 和 product_series 字段
只验证 PostgreSQL 迁移
只验证样例文档上传
只优化中文关键词检索
只做 records 页面
只做 system status 数据库检查
```

### 19.2 每次任务要求

每个 Codex 任务必须包含：

```text
目标
允许修改文件
禁止事项
执行命令
验收标准
完成输出
```

### 19.3 每次任务完成后必须输出

```text
新增文件
修改文件
执行了哪些命令
哪些命令真实成功
哪些命令失败
失败原因
是否涉及数据库迁移
是否涉及前端 build
是否改动 API 路径
是否仍符合第一版范围
```

### 19.4 不能接受的完成表述

以下表述不能作为完成依据：

```text
理论上可以
已预留
静态检查通过，所以功能完成
由于数据库不可用，但逻辑应当可用
后续再验证
```

必须明确区分：

```text
代码完成
静态检查完成
真实运行完成
数据库闭环完成
前端联调完成
```

---

## 20. 当前架构基线结论

Energy-Maintenance 第一版技术架构确定为：

```text
Vue3 + Vite + TypeScript + Element Plus 前端
FastAPI + SQLAlchemy + Alembic 后端
PostgreSQL 核心数据库
pypdf / python-docx 文档解析
PostgreSQL 文本检索 + 规则型问答生成
后续可扩展 pgvector、embedding、大模型和 OCR
最终部署到 LoongArch + Kylin 原生环境
使用 Python venv、systemd、Nginx、原生 PostgreSQL
不使用 Docker 作为正式部署路线
```

第一版业务技术主线为：

```text
华为/阳光电源光伏逆变器资料
        ↓
文档解析与知识切片
        ↓
PostgreSQL 入库
        ↓
检修问题检索
        ↓
真实 references
        ↓
结构化检修回答
        ↓
问答记录与诊断记录追溯
```

后续所有开发、接口、页面、数据库字段和验收标准，都必须围绕该技术架构执行。
---

## Task 02A 新版技术栈一致性补充

本补充用于压实第一版本技术路线，后续实现和验收以本节为一致性基线。

### A. 总体架构结论

- 系统采用 B/S 架构。
- 前端采用 Vue 3、Vite、TypeScript、Element Plus、Pinia、Axios。
- 后端采用 FastAPI、Uvicorn、Pydantic、SQLAlchemy 2.x、Alembic、PostgreSQL。
- 正式部署采用 LoongArch + Kylin 原生部署，使用 Python virtual environment、native PostgreSQL、Nginx、systemd。

### B. 模型服务与网关边界

第一版本预留 `Model Gateway`，业务模块只调用统一模型服务接口，不直接绑定 Ollama、vLLM、云厂商 SDK 或单一模型运行时。

- 本地小模型优先路线：llama.cpp + GGUF。
- 云端兼容路线：OpenAI-compatible API，用于对接 Qwen、DeepSeek 等兼容服务。
- Ollama 可作为开发期调试工具，但不是第一版本唯一依赖。
- vLLM 不作为第一版本主路线。

### C. 多模态与 OCR 边界

第一版本多模态输入边界包括：

- text：检修问题、故障现象、告警描述。
- device model：逆变器型号、产品系列。
- alarm code：告警码、故障码。
- fault image：故障现场图片上传与记录。
- image description：人工填写或后续识别得到的图片描述。

OCR 采用 `OCRService` 抽象预留，具体引擎在 LoongArch + Kylin 环境验证后选择，可选方向包括 PaddleOCR、RapidOCR、Tesseract。OCR 不阻塞 P0 闭环。

### D. 检索路线

P0 检索策略：

- PostgreSQL 结构化过滤。
- 关键词检索。
- alarm code 精确匹配。
- device model 匹配。
- device maintenance history 匹配。

P1 检索增强：

- pgvector + embedding 混合检索。
- 可在 PostgreSQL 闭环稳定后引入，不作为第一版本启动前置条件。

### E. 第一版本非主依赖

第一版本不把以下能力作为主路线或硬依赖：

- Docker 及 docker-compose。
- SQLite 作为正式数据库。
- vLLM 作为第一版本主模型运行路线。
- Neo4j、Milvus、FAISS、Chroma 作为第一版本硬依赖。

第一版本业务范围仍聚焦华为、阳光电源光伏逆变器检修知识检索、可追溯问答、故障诊断和作业辅助。

---

## Task 12 补充：Model Gateway 基础适配层

Task 12 在不修改数据库结构、不新增 Alembic migration、不替换现有规则型检索与诊断流程的前提下，补充统一模型网关基础设施。

- 默认 provider 为 `rule_based`，用于模型服务不可用时的规则型兜底。
- 本地模型预留 `local_llama_cpp`，通过 llama.cpp / GGUF 的 HTTP 兼容服务接入；本任务不安装、编译或下载模型。
- 云端模型预留 `cloud_openai`，通过 OpenAI-compatible API 接入；只有显式启用并配置 API key 时才允许调用。

---

## Task 14B Cloud Model Adapter Constraint

The `cloud_openai` route remains an optional OpenAI-compatible provider behind Model Gateway. A real cloud call is allowed only when `CLOUD_LLM_ENABLED=true`, `CLOUD_LLM_BASE_URL`, `CLOUD_LLM_API_KEY`, and `CLOUD_LLM_MODEL` are configured in `backend/.env`.

Provider status must distinguish `disabled`, `not_configured`, `not_checked`, `available`, and `unavailable`. `not_checked` means configuration exists but the status endpoint has not spent tokens to probe the provider.

Business modules must continue to preserve real `references`, `retrieved_chunks`, related history, and SOP steps. Cloud model output may only improve wording or supplemental explanation.
- 所有调用日志写入已有 `model_call_logs` 表，不在日志、前端或报告中暴露 API key。
- 现有 retrieval、diagnosis、SOP、task 业务模块仍保持当前规则型实现，不被 Model Gateway 强制替换。

正式部署路线仍为 LoongArch + Kylin + Python virtual environment + native PostgreSQL + systemd + Nginx，不使用 Docker 作为正式部署路线。
