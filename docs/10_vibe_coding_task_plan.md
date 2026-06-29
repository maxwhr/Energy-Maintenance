# 10 Vibe Coding 开发任务计划文档

**Document Name:** `10_vibe_coding_task_plan.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Core Scenario:** Huawei / Sungrow PV Inverter Maintenance System  
**Development Mode:** High-standard Vibe Coding with Strict Acceptance  

---

## 1. 文档目的

本文档用于将 Energy-Maintenance 第一版后续开发拆解为可执行、可验收、可回滚的小任务，作为 Codex 或其他 AI 编码工具的直接开发任务计划。

本项目第一版已经明确收敛为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

本项目采用高标准 vibe coding 路线，目标不是先开发一个粗糙雏形再大量返工，而是通过完整、详细、可执行的前期文档，让后续 AI 编码尽量一次性接近最终可交付标准。

因此，后续开发必须遵循：

```text
小任务
小改动
强约束
真实运行
真实入库
真实 references
明确验收
不伪造完成结果
```

本文档不用于写行业背景，不用于写汇报材料，而是用于指导 Codex 逐步开发。

---

## 2. 已确定的项目基线

后续所有任务必须遵守以下基线。

### 2.1 项目名称

```text
Energy-Maintenance
```

### 2.2 第一版业务范围

```text
面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统
```

### 2.3 第一版支持厂家

```text
huawei：华为
sungrow：阳光电源
```

### 2.4 第一版支持设备

```text
pv_inverter：光伏逆变器
```

### 2.5 第一版支持产品系列

```text
SUN2000
FusionSolar
SG
```

### 2.6 第一版核心功能

```text
知识库管理
文档上传解析
知识切片入库
检修问答
来源追溯
故障诊断
检修任务
记录追溯
系统状态
LoongArch + Kylin 原生部署准备
```

### 2.7 正式部署路线

```text
LoongArch + Kylin + Python venv + PostgreSQL + systemd + Nginx
```

禁止将 Docker 作为正式部署路线。

---

## 3. 任务执行总原则

### 3.1 每次只做一个小任务

Codex 每轮开发应只执行一个明确任务。

禁止一轮同时做：

```text
数据库大改
前端大改
接口大改
RAG 大改
部署脚本大改
```

这会导致问题难以定位。

---

### 3.2 每个任务必须有验收命令

任务完成不能只说“已修改”。

必须尽量执行：

```text
后端编译检查
数据库迁移
API curl
前端 build
数据库查询
```

如果因环境限制无法执行，必须明确说明未执行原因。

---

### 3.3 不允许伪造验收结果

Codex 输出中禁止出现：

```text
已通过真实入库测试
```

但实际没有连接 PostgreSQL。

禁止出现：

```text
RAG 已完成
```

但 references 不是来自真实 `knowledge_chunks`。

禁止出现：

```text
部署已完成
```

但未在 LoongArch + Kylin 环境执行。

---

### 3.4 修改前必须先读文档

每次任务开始前，Codex 应至少参考：

```text
AGENTS.md
docs/01_project_scope_and_product_requirements.md
docs/02_technical_stack_and_architecture.md
docs/03_database_schema_design.md
docs/04_api_contract_design.md
docs/09_testing_acceptance_and_quality_spec.md
```

涉及特定模块时，还应读取对应文档：

```text
前端任务读取 05
知识库任务读取 06
问答/诊断任务读取 07
部署任务读取 08
```

---

## 4. 任务输出格式要求

每次 Codex 完成任务后，必须按以下格式输出。

```text
# Task Result

## 1. Task Summary
本次任务目标：

## 2. Modified Files
- ...

## 3. Implementation Details
- ...

## 4. Commands Executed
- command: ...
  result: passed / failed

## 5. Acceptance Results
- Database migration: passed / failed / not executed
- Backend API: passed / failed / not executed
- Frontend build: passed / failed / not executed
- Real PostgreSQL write: passed / failed / not executed

## 6. Known Issues
- ...

## 7. Next Suggested Task
- ...
```

如果某个命令未执行，必须写：

```text
not executed
原因：...
```

不得省略。

---

## 5. 后续开发任务总览

建议开发顺序如下：

```text
Task 01：项目范围收敛与文案清理
Task 02：数据库字段补齐与 Alembic 迁移
Task 03：PostgreSQL 真实连接与迁移验收
Task 04：华为/阳光样例知识库资料补充
Task 05：知识库上传解析真实闭环验收
Task 06：中文关键词检索与 references 真实性修正
Task 07：检修问答 qa_records 真实保存闭环
Task 08：故障诊断规则库与 diagnosis_records 保存
Task 09：检修任务管理与任务状态流转
Task 10：记录追溯页面与记录接口联调
Task 11：系统状态页与统计接口完善
Task 12：前端页面范围收敛与交互完善
Task 13：端到端真实业务闭环验收
Task 14：LoongArch + Kylin 部署脚本与文档落地
Task 15：最终质量检查与比赛演示数据准备
```

---

# Task 01：项目范围收敛与文案清理

## 1. 任务目标

检查当前项目中所有文案、README、前端页面、样例数据和接口描述，确保第一版范围严格收敛到：

```text
华为与阳光电源光伏逆变器检修
```

避免仍出现泛化表述。

---

## 2. 允许修改文件

```text
README.md
AGENTS.md
docs/*.md
backend/README.md
frontend/src/views/*.vue
frontend/src/components/*.vue
frontend/src/router/index.ts
backend/app/core/config.py
backend/app/api/**/*.py
```

---

## 3. 禁止事项

```text
1. 不开发新功能
2. 不改数据库结构
3. 不改 API 路径
4. 不引入新依赖
5. 不删除已有业务代码
```

---

## 4. 检查关键词

需要查找并判断是否需要替换：

```text
泛新能源
新能源设备
储能电池
箱式变压器
电力巡检
机器人
摩托车
发动机
车辆维修
教育平台
通用客服
```

如果作为“未来扩展”出现可以保留，但不能作为第一版主线。

---

## 5. 验收标准

```text
1. README 中项目定位为华为/阳光电源光伏逆变器检修
2. 前端页面不再展示泛新能源设备作为主线
3. 下拉选项中厂家仅包含 huawei / sungrow
4. 设备类型第一版仅展示 pv_inverter
5. 系统状态页说明 LoongArch + Kylin 原生部署
```

---

## 6. 建议 Codex 提示词

```text
请执行 Task 01：项目范围收敛与文案清理。

你必须先阅读：
- AGENTS.md
- docs/01_project_scope_and_product_requirements.md
- docs/02_technical_stack_and_architecture.md
- docs/05_frontend_page_and_interaction_spec.md

本次任务只做范围和文案收敛，不开发新功能，不改数据库结构，不改 API 路径。

请检查 README、docs、backend、frontend 中是否仍有泛新能源设备、储能设备、箱式变压器、电力巡检、车辆维修、摩托车、教育平台等偏离第一版范围的主线表述。

第一版主线必须统一为：
面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

第一版厂家：
- huawei：华为
- sungrow：阳光电源

第一版设备类型：
- pv_inverter：光伏逆变器

完成后按 Task Result 格式输出修改文件、修改内容、未修改原因和是否还有范围残留。
```

---

# Task 02：数据库字段补齐与 Alembic 迁移

## 1. 任务目标

检查现有 SQLAlchemy models 和 Alembic migrations，确保核心表具备第一版业务需要的字段。

重点字段：

```text
manufacturer
product_series
device_type
document_type
fault_type
alarm_code
references
retrieved_chunks
source_trace_id
```

---

## 2. 允许修改文件

```text
backend/app/models/*.py
backend/app/schemas/*.py
backend/app/repositories/*.py
backend/alembic/versions/*.py
backend/alembic/env.py
backend/app/core/database.py
```

---

## 3. 禁止事项

```text
1. 不改 API 路径
2. 不改前端页面
3. 不开发 RAG 逻辑
4. 不使用 SQLite 代替 PostgreSQL
5. 不删除已有表数据字段，除非明确确认
```

---

## 4. 必须检查的表

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

---

## 5. 字段要求

### knowledge_documents

必须包含：

```text
manufacturer
product_series
model
device_type
document_type
source
file_name
file_path
file_size
file_ext
page_count
parse_status
parser_name
chunk_count
summary
error_message
metadata_json
parsed_at
status
created_at
updated_at
```

### knowledge_chunks

必须包含：

```text
document_id
manufacturer
product_series
device_type
document_type
chunk_index
content
section_title
char_count
page_number
embedding_status
metadata_json
status
created_at
updated_at
```

### qa_records

必须包含：

```text
question
normalized_query
manufacturer
product_series
device_type
document_type
answer
references
retrieved_chunks
suggested_steps
confidence
trace_id
created_at
updated_at
```

### diagnosis_records

必须包含：

```text
manufacturer
product_series
device_type
device_name
model
fault_type
alarm_code
alarm_info
fault_description
device_status
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
created_at
updated_at
```

### maintenance_tasks

必须包含：

```text
title
manufacturer
product_series
device_type
device_id
device_name
model
fault_type
alarm_code
fault_description
priority
task_status
assignee
due_date
source_type
source_trace_id
suggested_steps
result_summary
completion_notes
created_at
updated_at
completed_at
```

---

## 6. 验收标准

```text
1. SQLAlchemy models 字段齐全
2. Pydantic schemas 字段同步
3. Alembic migration 能生成或已存在
4. alembic upgrade head 能在 PostgreSQL 上执行
5. 不破坏已有 API
```

---

## 7. 建议 Codex 提示词

```text
请执行 Task 02：数据库字段补齐与 Alembic 迁移。

你必须先阅读：
- docs/03_database_schema_design.md
- docs/04_api_contract_design.md
- docs/09_testing_acceptance_and_quality_spec.md

本次任务只处理数据库模型、schema 和 migration，不开发前端，不开发新业务功能，不改 API 路径。

请检查核心表：
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks

根据 docs/03_database_schema_design.md 补齐缺失字段，生成 Alembic migration。

完成后尝试执行：
cd backend
alembic -c alembic.ini upgrade head

如果 PostgreSQL 不可连接，必须明确说明未执行原因，不能宣称迁移通过。
```

---

# Task 03：PostgreSQL 真实连接与迁移验收

## 1. 任务目标

确保项目能真实连接 PostgreSQL，并真实执行 Alembic 迁移。

这是进入核心业务开发前的必要任务。

---

## 2. 允许修改文件

```text
backend/.env.example
backend/README.md
README.md
backend/app/core/config.py
backend/app/core/database.py
backend/alembic/env.py
```

---

## 3. 禁止事项

```text
1. 不使用 SQLite 作为替代
2. 不把 Docker 写成正式部署路线
3. 不跳过真实 PostgreSQL 连接
4. 不修改业务功能
```

---

## 4. 验收命令

```bash
cd backend
alembic -c alembic.ini upgrade head
```

数据库检查：

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

必须看到核心表。

---

## 5. 验收标准

```text
1. DATABASE_URL 正确读取
2. PostgreSQL 可连接
3. alembic upgrade head 成功
4. 核心表创建成功
5. /api/system/status 能显示 database_status = connected
```

---

## 6. 建议 Codex 提示词

```text
请执行 Task 03：PostgreSQL 真实连接与迁移验收。

本次任务目标不是开发新功能，而是让 Energy-Maintenance 真实连接 PostgreSQL 并执行 Alembic 迁移。

请检查：
- backend/.env.example
- backend/app/core/config.py
- backend/app/core/database.py
- backend/alembic/env.py
- backend/README.md

要求：
1. DATABASE_URL 使用 postgresql+psycopg
2. 不使用 SQLite
3. 不使用 Docker 作为正式路线
4. 真实执行 alembic upgrade head
5. 如果数据库不可连接，明确输出失败原因和用户需要执行的 PostgreSQL 启动/建库命令

完成后按 Task Result 格式输出。
```

---

# Task 04：华为/阳光样例知识库资料补充

## 1. 任务目标

补充用于验收的最小样例资料，保证即使没有大型官方 PDF，也能完成知识库、检索问答和故障诊断闭环。

---

## 2. 允许修改文件

```text
backend/storage/samples/*.txt
backend/storage/samples/*.md
README.md
docs/06_knowledge_base_and_document_processing_spec.md
```

---

## 3. 必须新增样例

```text
sample_huawei_sun2000_low_insulation.txt
sample_huawei_fusionsolar_communication.txt
sample_sungrow_sg_overtemperature.txt
sample_sungrow_sg_mppt_low_power.txt
```

---

## 4. 样例内容要求

样例必须包含：

```text
厂家
产品系列
设备类型
故障现象
可能原因
排查步骤
安全注意事项
推荐处理措施
```

不得只写简单测试文本。

---

## 5. 禁止事项

```text
1. 不使用虚假品牌
2. 不复制大段受版权保护的官方手册
3. 不写成泛新能源资料
4. 不加入储能电池、箱变等非第一版内容
```

---

## 6. 验收标准

```text
1. 四个样例文件存在
2. 内容围绕华为/阳光光伏逆变器
3. 每个文件长度足够生成至少 1 个 chunk
4. 能支持问答命中关键词
```

---

# Task 05：知识库上传解析真实闭环验收

## 1. 任务目标

真实跑通：

```text
上传样例资料 -> 解析文本 -> 生成 chunks -> 写入 PostgreSQL -> 查询 chunks
```

---

## 2. 允许修改文件

```text
backend/app/knowledge/*.py
backend/app/services/knowledge_service.py
backend/app/repositories/knowledge_repository.py
backend/app/api/*knowledge*.py
backend/app/schemas/knowledge.py
```

---

## 3. 禁止事项

```text
1. 不开发问答逻辑
2. 不改前端
3. 不引入 OCR
4. 不使用模拟 chunks
```

---

## 4. 验收命令

上传华为样例：

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_huawei_sun2000_low_insulation.txt" \
  -F "manufacturer=huawei" \
  -F "product_series=SUN2000" \
  -F "device_type=pv_inverter" \
  -F "document_type=alarm_code" \
  -F "source=local_sample"
```

查询文档：

```bash
curl "http://127.0.0.1:8000/api/knowledge/documents?manufacturer=huawei"
```

查询 chunks：

```bash
curl http://127.0.0.1:8000/api/knowledge/documents/{document_id}/chunks
```

---

## 5. 验收标准

```text
1. parse_status = parsed
2. chunk_count > 0
3. knowledge_chunks.content 不为空
4. chunk_count 与实际 chunks 数量一致
5. 上传失败时 error_message 明确
```

---

# Task 06：中文关键词检索与 references 真实性修正

## 1. 任务目标

实现或修正基于 `knowledge_chunks` 的中文关键词检索，保证问答 references 来自真实数据库。

---

## 2. 允许修改文件

```text
backend/app/rag/retriever.py
backend/app/services/retrieval_service.py
backend/app/repositories/knowledge_repository.py
backend/app/schemas/retrieval.py
```

---

## 3. 禁止事项

```text
1. 不接入真实大模型
2. 不接入 embedding
3. 不使用前端假数据
4. 不编造 references
```

---

## 4. 检索必须支持

```text
query
manufacturer
product_series
device_type
document_type
top_k
```

---

## 5. 验收标准

```text
1. 华为绝缘阻抗低问题能命中华为样例 chunks
2. 阳光过温问题能命中阳光样例 chunks
3. references 中 document_id 和 chunk_index 真实存在
4. 无结果时 references = []
5. top_k 最大 10
```

---

# Task 07：检修问答 qa_records 真实保存闭环

## 1. 任务目标

完善 `/api/retrieval/query`，确保每次问答都保存 `qa_records`。

---

## 2. 允许修改文件

```text
backend/app/services/retrieval_service.py
backend/app/repositories/record_repository.py
backend/app/models/record.py
backend/app/schemas/retrieval.py
backend/app/schemas/record.py
backend/app/api/*retrieval*.py
backend/app/api/*records*.py
```

---

## 3. 禁止事项

```text
1. 不伪造 qa_records
2. 不使用内存列表保存记录
3. 不改数据库连接
```

---

## 4. 验收标准

```text
1. /api/retrieval/query 返回 trace_id
2. qa_records 中能查到该 trace_id
3. references 和 retrieved_chunks 被保存
4. /api/retrieval/records 或 /api/record-center/search 能查询记录
5. 服务重启后记录仍存在
```

---

# Task 08：故障诊断规则库与 diagnosis_records 保存

## 1. 任务目标

完善故障诊断模块，使其围绕光伏逆变器典型故障输出结构化结果，并保存诊断记录。

---

## 2. 允许修改文件

```text
backend/app/maintenance/*.py
backend/app/services/maintenance_service.py
backend/app/repositories/record_repository.py
backend/app/models/record.py
backend/app/schemas/maintenance.py
backend/app/api/*maintenance*.py
backend/app/api/*records*.py
```

---

## 3. 必须支持的故障类型

```text
low_insulation_resistance
over_temperature
fan_fault
communication_interruption
device_offline
mppt_abnormal
low_power_generation
grid_connection_fault
ac_overvoltage
ac_undervoltage
```

---

## 4. 必须输出字段

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

---

## 5. 验收标准

```text
1. 阳光过温诊断有原因、步骤、安全提示、处理措施
2. 华为通信中断诊断有通信链路排查建议
3. diagnosis_records 写入成功
4. /api/diagnosis/records 或 /api/record-center/search 能查询记录
5. safety_notes 不为空
```

---

# Task 09：检修任务管理与任务状态流转

## 1. 任务目标

完善检修任务模块，实现任务创建、列表、详情、状态更新和来源追溯。

---

## 2. 允许修改文件

```text
backend/app/models/maintenance.py
backend/app/schemas/maintenance.py
backend/app/repositories/maintenance_repository.py
backend/app/services/maintenance_service.py
backend/app/api/*maintenance*.py
frontend/src/views/MaintenanceTaskView.vue
frontend/src/api/maintenance.ts
```

---

## 3. 必须支持状态

```text
pending
in_progress
completed
cancelled
```

---

## 4. 状态流转规则

允许：

```text
pending -> in_progress
pending -> cancelled
in_progress -> completed
in_progress -> cancelled
```

不允许：

```text
completed -> pending
cancelled -> in_progress
```

---

## 5. 验收标准

```text
1. 能创建任务
2. task_status 默认 pending
3. 能更新为 in_progress
4. 能更新为 completed
5. completed 时保存 result_summary
6. 非法状态流转返回 409
7. 列表和详情能查询任务
```

---

# Task 10：记录追溯页面与记录接口联调

## 1. 任务目标

实现或完善记录追溯页面，展示问答记录和诊断记录。

---

## 2. 允许修改文件

```text
frontend/src/views/RecordCenterView.vue
frontend/src/api/records.ts
frontend/src/types/records.ts
frontend/src/components/ReferenceList.vue
backend/app/api/*records*.py
backend/app/schemas/record.py
backend/app/repositories/record_repository.py
```

---

## 3. 页面必须展示

```text
qa_records
diagnosis_records
trace_id
references
retrieved_chunks
suggested_steps
inspection_steps
safety_notes
created_at
```

---

## 4. 验收标准

```text
1. 问答后能在记录追溯页看到记录
2. 诊断后能在记录追溯页看到记录
3. references 可见
4. trace_id 可见
5. 刷新页面后记录仍存在
```

---

# Task 11：系统状态页与统计接口完善

## 1. 任务目标

完善 `/api/system/status` 和系统状态页，真实展示服务状态、数据库状态和核心数据统计。

---

## 2. 允许修改文件

```text
backend/app/api/*system*.py
backend/app/services/system_service.py
backend/app/repositories/*.py
frontend/src/views/SystemStatusView.vue
frontend/src/views/DashboardView.vue
frontend/src/api/system.ts
```

---

## 3. 必须统计

```text
document_count
chunk_count
qa_record_count
diagnosis_record_count
maintenance_task_count
database_status
```

---

## 4. 验收标准

```text
1. 数据库连通时 database_status = connected
2. 数据库不可用时不能显示 connected
3. 统计数据来自 PostgreSQL
4. Dashboard 和 SystemStatusView 均能显示
```

---

# Task 12：前端页面范围收敛与交互完善

## 1. 任务目标

完善前端页面，使其符合 `05_frontend_page_and_interaction_spec.md`。

---

## 2. 允许修改文件

```text
frontend/src/views/*.vue
frontend/src/components/*.vue
frontend/src/api/*.ts
frontend/src/types/*.ts
frontend/src/router/index.ts
frontend/src/stores/*.ts
```

---

## 3. 必须完善页面

```text
DashboardView
KnowledgeBaseView
RetrievalChatView
FaultDiagnosisView
MaintenanceTaskView
RecordCenterView
SystemStatusView
```

---

## 4. 验收标准

```text
1. npm run build 成功
2. 页面文案聚焦华为/阳光光伏逆变器
3. 知识库页面可上传资料
4. 问答页展示 references
5. 诊断页突出 safety_notes
6. 任务页可创建和更新任务
7. 记录页可展示 qa_records / diagnosis_records
8. 系统状态页展示数据库状态
```

---

# Task 13：端到端真实业务闭环验收

## 1. 任务目标

不开发新功能，只做完整闭环验证和必要小修复。

---

## 2. 验收流程

```text
1. 启动 PostgreSQL
2. alembic upgrade head
3. 启动后端
4. 启动前端
5. 上传华为样例
6. 上传阳光样例
7. 查询 chunks
8. 华为问题问答
9. 阳光问题问答
10. 查看 qa_records
11. 执行故障诊断
12. 查看 diagnosis_records
13. 创建检修任务
14. 更新任务状态
15. 查看 Dashboard 和 SystemStatus
```

---

## 3. 禁止事项

```text
1. 不开发新功能
2. 不大规模重构
3. 不用假数据绕过失败
4. 不跳过 PostgreSQL
```

---

## 4. 验收标准

```text
完整闭环全部通过，才可进入部署任务。
```

---

# Task 14：LoongArch + Kylin 部署脚本与文档落地

## 1. 任务目标

将 `08_deployment_and_loongarch_kylin_spec.md` 落地为部署脚本、systemd 示例、Nginx 示例和 README 部署说明。

---

## 2. 允许修改文件

```text
deploy/
deploy/systemd/energy-maintenance-backend.service
deploy/nginx/energy-maintenance.conf
scripts/deploy_backend.sh
scripts/deploy_frontend.sh
scripts/backup_database.sh
scripts/health_check.sh
README.md
backend/README.md
```

---

## 3. 禁止事项

```text
1. 不新增 Dockerfile
2. 不新增 docker-compose 作为正式部署方案
3. 不写成 x86 专用部署
4. 不要求必须安装大型本地模型
```

---

## 4. 验收标准

```text
1. systemd service 示例存在
2. Nginx 配置示例存在
3. 备份脚本存在
4. 健康检查脚本存在
5. README 明确 LoongArch + Kylin 原生部署
6. README 明确 Docker 不是正式路线
```

---

# Task 15：最终质量检查与比赛演示数据准备

## 1. 任务目标

在提交或演示前进行最终整理，确保系统、文档、样例数据、演示流程一致。

---

## 2. 检查内容

```text
1. README 项目描述
2. docs 文档完整性
3. AGENTS.md 开发约束
4. 前端页面文案
5. 样例资料
6. 数据库迁移
7. API 闭环
8. 前端闭环
9. 部署说明
10. 演示脚本
```

---

## 3. 演示数据建议

准备至少以下演示场景：

```text
场景 1：华为 SUN2000 绝缘阻抗低告警排查
场景 2：华为 FusionSolar 设备离线 / 通信中断排查
场景 3：阳光 SG 系列过温降额处理
场景 4：阳光 SG 系列 MPPT 异常与功率偏低分析
场景 5：基于问答或诊断生成检修任务
场景 6：记录追溯查看 references 和 trace_id
```

---

## 4. 验收标准

```text
1. 所有演示场景可稳定复现
2. references 真实可见
3. trace_id 真实可见
4. 数据库记录真实存在
5. 前端无明显假数据
6. 系统范围不发散
```

---

## 6. Codex 总提示词模板

后续每次发给 Codex 的任务都建议使用以下模板。

```text
你现在在 Energy-Maintenance 项目中工作。

项目第一版范围：
面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

第一版厂家：
- huawei：华为
- sungrow：阳光电源

第一版设备：
- pv_inverter：光伏逆变器

正式部署路线：
LoongArch + Kylin + Python venv + PostgreSQL + systemd + Nginx。
不要将 Docker 作为正式部署方案。

请先阅读：
- AGENTS.md
- docs/01_project_scope_and_product_requirements.md
- docs/02_technical_stack_and_architecture.md
- docs/03_database_schema_design.md
- docs/04_api_contract_design.md
- docs/09_testing_acceptance_and_quality_spec.md
以及本次任务相关文档。

本次只执行：
[填写任务编号和任务名称]

要求：
1. 只做本任务范围内的修改
2. 不要大规模重构
3. 不要扩展到泛新能源设备
4. 不要使用 SQLite 替代 PostgreSQL
5. 不要伪造 references
6. 不要用前端假数据冒充真实闭环
7. 没有真实执行的命令必须写 not executed
8. 完成后按 Task Result 格式输出
```

---

## 7. 任务优先级建议

当前最优先级应为：

```text
P0：
Task 01
Task 02
Task 03

P1：
Task 04
Task 05
Task 06
Task 07
Task 08
Task 09
Task 10
Task 11
Task 12

P2：
Task 13
Task 14
Task 15
```

解释：

```text
如果数据库字段和 PostgreSQL 真实连接不稳定，后面的 RAG、问答、诊断、前端展示都会变成假闭环。
```

因此，开发顺序应坚持：

```text
先数据库和真实入库
再检索和问答
再诊断和任务
再前端完善
最后部署和演示
```

---

## 8. 与其他文档关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
03_database_schema_design.md
04_api_contract_design.md
05_frontend_page_and_interaction_spec.md
06_knowledge_base_and_document_processing_spec.md
07_retrieval_qa_and_fault_diagnosis_spec.md
08_deployment_and_loongarch_kylin_spec.md
09_testing_acceptance_and_quality_spec.md
```

其中：

- `01` 定义产品范围；
- `02` 定义技术架构；
- `03` 定义数据库结构；
- `04` 定义 API 契约；
- `05` 定义前端页面；
- `06` 定义知识库处理；
- `07` 定义检索问答和故障诊断；
- `08` 定义部署路线；
- `09` 定义验收标准；
- `10` 定义后续 Codex 任务计划。

---

## 9. 下一步建议

本文档确认后，还建议补充一份：

```text
AGENTS.md
```

`AGENTS.md` 是 Codex 每次开发前必须读取的项目开发规则入口。

它应包含：

```text
项目范围
禁止事项
目录结构
编码规范
数据库规范
接口规范
测试验收规范
Codex 输出格式
```

如果已有 AGENTS.md，应根据当前 10 份文档进行重写或强化。
---

## Task 02A 后续任务拆分补充

本补充将新版技术栈、功能边界和数据库对齐工作拆成后续小任务，避免在单轮开发中混入大范围重构。

### A. 已完成或本轮目标

- Task 02A：新版技术栈、功能边界、数据库设计一致性静态审查。

### B. 后续建议顺序

- Task 02B：数据库模型字段补齐与 Alembic migration。
- Task 03：PostgreSQL 真实连接与迁移验收。
- Task 04：华为、阳光电源样例文档准备。
- Task 05：知识上传、解析、切片、入库真实闭环。
- Task 06：PostgreSQL 关键词检索和真实 references。
- Task 07：qa_records 持久化与追溯中心。
- Task 08：故障诊断记录、图片上传和 safety_notes 验收。
- Task 09：设备台账与设备检修历史。
- Task 10：SOP 模板与执行记录。
- Task 11：知识贡献、审核、模型输出纠错。
- Task 12：Model Gateway 基础配置与调用日志。
- Task 13：前端页面补齐与交互验收。
- Task 14：LoongArch + Kylin 原生部署脚本。
- Task 15：最终演示与上交材料整理。

### C. Task 02B 注意事项

Task 02B 可以修改 model、schema、migration、repository、service 和 API，但应继续保持 `/api` 对外路径，不引入 Docker、SQLite、embedding、pgvector、真实大模型或新架构路线。
