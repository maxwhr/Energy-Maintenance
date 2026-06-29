# 09 测试、验收与质量规范文档

## Task 16 Final Hardening Acceptance

Task 16 acceptance must be reported honestly. Do not claim real PostgreSQL migration, cloud model calls, OCR, pgvector, or LoongArch/Kylin deployment unless they were actually executed.

Required commands:

```powershell
cd frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
uv run python -m compileall app
uv run python -m alembic -c alembic.ini current
```

`alembic current` must remain `20260601_0002`.

Do not run during Task 16:

```text
alembic revision
alembic upgrade head
```

Runtime smoke:

```powershell
cd "D:\Work Space\Energy-Maintenance"
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
```

Default final smoke validates static frontend fallback, OpenAPI pages, login, `/api/auth/me`, system status/statistics, devices, knowledge, retrieval records, diagnosis records, SOP templates, tasks, record center, review, corrections, and model gateway status. It skips retrieval query writes by default to avoid creating extra `qa_records`; use `-IncludeRetrievalQuery` only when a traceable write smoke is required.

Data safety checks:

- `backend/scripts/cleanup_dev_test_data.py` must be dry-run unless explicitly confirmed.
- It must not physically delete uploaded files.
- It should skip rows that cannot be safely soft-archived without foreign-key risk.

Task 18B contribution-flow checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python scripts/seed_final_demo_data.py
uv run python scripts/check_contribution_flow.py
uv run python -m alembic -c alembic.ini current

cd ..
powershell -ExecutionPolicy Bypass -File scripts/final_smoke_test.ps1 -IncludeRetrievalQuery
```

Acceptance points:

- engineer can create, edit, and submit a contribution.
- expert/admin can request changes, approve, reject, convert to document, and archive.
- converted contribution creates real `knowledge_documents` and `knowledge_chunks`.
- retrieval can hit converted contribution chunks and returns real references.
- `record-center` can search `record_type=knowledge_contribution`.
- viewer can read approved/converted contributions but cannot create or review.
- no Alembic revision or `alembic upgrade head` is required for Task 18B.

Task 18C knowledge-graph checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini heads
uv run python -m alembic -c alembic.ini current
uv run python -m alembic -c alembic.ini upgrade head
uv run python -m alembic -c alembic.ini current
uv run python scripts/seed_demo_knowledge_graph.py
uv run python scripts/check_knowledge_graph_flow.py

cd ..\frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
```

Acceptance points:

- `kg_nodes`, `kg_edges`, `kg_node_aliases`, `kg_evidence_links`, `kg_extraction_runs`, and `kg_candidates` are created by Alembic.
- `/api/kg/overview` works for authenticated users.
- extraction from an approved parsed document creates pending candidates.
- expert/admin can approve node and edge candidates.
- viewer cannot approve candidates.
- approved graph data has evidence links back to source knowledge data.
- no Neo4j, pgvector, embedding, OCR, Docker, or SQLite is introduced.

**Document Name:** `09_testing_acceptance_and_quality_spec.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Core Scenario:** Huawei / Sungrow PV Inverter Maintenance System  
**Testing Focus:** Real PostgreSQL Closed-loop Verification  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版的测试、验收和质量标准，作为后续 vibe coding、Codex 开发、人工审核、部署验证和比赛演示前检查的统一依据。

本项目第一版已经明确收敛为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

因此，验收不能只停留在：

```text
代码能编译
页面能打开
接口有返回
文档写得完整
```

而必须验证真实业务闭环：

```text
PostgreSQL 可连接
Alembic 迁移成功
华为 / 阳光样例资料可上传
knowledge_documents 真实写入
knowledge_chunks 真实生成
检索问答能命中真实 chunks
references 来自真实知识库
qa_records 真实保存
故障诊断结果真实保存
检修任务真实创建和流转
前端页面能展示真实数据
```

本文档的核心原则是：

```text
没有真实执行，就不能宣称完成。
没有真实入库，就不能宣称闭环完成。
没有真实 references，就不能宣称 RAG 完成。
```

---

## 2. 总体验收原则

### 2.1 真实运行优先

第一版所有核心功能必须经过真实运行验证。

禁止只用以下内容作为完成依据：

```text
1. 静态代码检查通过
2. TypeScript 编译通过
3. Python import 成功
4. OpenAPI 能打开
5. 前端页面有 UI
6. 返回模拟数据
7. README 中写了命令但未执行
```

这些只能作为基础质量检查，不能替代业务验收。

---

### 2.2 数据库真实闭环优先

本项目核心数据必须真实写入 PostgreSQL。

以下表必须参与验收：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

验收时必须能够证明：

```text
1. 数据不是内存模拟
2. 服务重启后数据仍存在
3. API 返回数据来自 PostgreSQL
4. 前端展示数据来自 API
```

---

### 2.3 references 真实性优先

检索问答和故障诊断中的 references 是系统可信度核心。

必须满足：

```text
references 中每一条来源都能追溯到真实 knowledge_chunks
```

禁止：

```text
1. 编造文档标题
2. 编造页码
3. 编造章节标题
4. 编造来源
5. 无检索结果时强行返回 references
```

---

### 2.4 范围收敛优先

验收时必须检查系统是否仍保持第一版业务范围：

```text
华为
阳光电源
光伏逆变器
SUN2000 / FusionSolar / SG
告警排查
故障诊断
检修任务
记录追溯
```

如发现系统文案、字段、页面、样例或接口扩散到以下内容，应视为范围偏移：

```text
泛新能源设备
储能电池系统
箱式变压器
电力巡检设备
汽车维修
摩托车维修
教育系统
通用客服机器人
```

---

## 3. 测试分层

第一版测试分为七层：

```text
1. 代码质量检查
2. 数据库迁移测试
3. 后端 API 测试
4. 知识库文档处理测试
5. 检索问答与故障诊断测试
6. 前端页面交互测试
7. LoongArch + Kylin 部署验收
```

不同层级的测试不能互相替代。

例如：

```text
前端 build 成功 ≠ 系统验收完成
后端 health 正常 ≠ 知识库闭环完成
OpenAPI 正常 ≠ 问答 references 真实
```

---

## 4. 代码质量检查

### 4.1 Python 基础检查

建议执行：

```bash
cd backend
python -m compileall app
```

如果项目使用 ruff：

```bash
ruff check app
```

如果项目使用 mypy：

```bash
mypy app
```

第一版不强制 mypy 全量通过，但不应存在明显语法错误、未导入模块、循环导入导致服务无法启动等问题。

---

### 4.2 前端基础检查

建议执行：

```bash
cd frontend
npm install
npm run build
```

如有 lint 脚本：

```bash
npm run lint
```

前端必须满足：

```text
1. npm run build 成功
2. 无明显 TypeScript 类型错误
3. 页面路由可访问
4. API 封装路径统一使用 /api
```

---

### 4.3 禁止把静态检查当作最终验收

以下输出不能作为最终完成证明：

```text
compileall passed
ruff passed
npm run build passed
openapi.json accessible
```

这些只能说明基础代码质量合格，不能说明业务闭环完成。

---

## 5. 数据库迁移验收

### 5.1 PostgreSQL 连接验收

执行前必须确认 PostgreSQL 可用。

Linux / Kylin：

```bash
systemctl status postgresql
ss -lntp | grep 5432
```

Windows 本地开发：

```powershell
Test-NetConnection 127.0.0.1 -Port 5432
```

数据库连接测试：

```bash
psql "postgresql://energy_user:energy_password@127.0.0.1:5432/energy_maintenance" -c "SELECT version();"
```

必须真实返回 PostgreSQL 版本。

---

### 5.2 Alembic 迁移验收

执行：

```bash
cd backend
alembic -c alembic.ini upgrade head
```

或：

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

必须真实连接 PostgreSQL 并执行成功。

不允许只执行：

```bash
alembic upgrade head --sql
```

离线 SQL 生成不能替代真实迁移验收。

---

### 5.3 核心表存在性验收

迁移后执行：

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

必须包含：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

建议包含：

```text
users
devices
operation_logs
model_call_logs
```

---

### 5.4 核心字段验收

必须检查以下字段存在。

#### knowledge_documents

```text
manufacturer
product_series
device_type
document_type
parse_status
chunk_count
file_path
file_ext
error_message
metadata_json
```

#### knowledge_chunks

```text
document_id
manufacturer
product_series
device_type
document_type
chunk_index
content
section_title
embedding_status
```

#### qa_records

```text
question
answer
references
retrieved_chunks
suggested_steps
confidence
trace_id
```

#### diagnosis_records

```text
fault_description
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

#### maintenance_tasks

```text
title
manufacturer
product_series
device_type
fault_type
priority
task_status
source_type
source_trace_id
```

---

## 6. 后端服务启动验收

### 6.1 本地启动

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如使用 uv：

```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

### 6.2 健康检查

```bash
curl http://127.0.0.1:8000/api/health
```

必须返回：

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "running"
  }
}
```

---

### 6.3 系统状态检查

```bash
curl http://127.0.0.1:8000/api/system/status
```

必须真实反映数据库状态。

如果数据库不可用，不能返回：

```text
database_status = connected
```

---

### 6.4 OpenAPI 检查

```bash
curl http://127.0.0.1:8000/openapi.json
```

必须包含核心接口：

```text
/api/knowledge/documents/upload
/api/retrieval/query
/api/diagnosis/analyze
/api/maintenance/tasks
/api/retrieval/records
/api/diagnosis/records
```

---

## 7. 知识库上传与切片验收

### 7.1 样例资料要求

验收前必须准备至少 4 个样例文档：

```text
sample_huawei_sun2000_low_insulation.txt
sample_huawei_fusionsolar_communication.txt
sample_sungrow_sg_overtemperature.txt
sample_sungrow_sg_mppt_low_power.txt
```

样例文档必须包含真实检修语义，不得只写：

```text
test
hello
sample content
```

---

### 7.2 华为绝缘阻抗低样例上传

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_huawei_sun2000_low_insulation.txt" \
  -F "manufacturer=huawei" \
  -F "product_series=SUN2000" \
  -F "device_type=pv_inverter" \
  -F "document_type=alarm_code" \
  -F "source=local_sample"
```

必须满足：

```text
parse_status = parsed
chunk_count > 0
manufacturer = huawei
product_series = SUN2000
device_type = pv_inverter
document_type = alarm_code
```

---

### 7.3 阳光过温样例上传

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_sungrow_sg_overtemperature.txt" \
  -F "manufacturer=sungrow" \
  -F "product_series=SG" \
  -F "device_type=pv_inverter" \
  -F "document_type=sop" \
  -F "source=local_sample"
```

必须满足：

```text
parse_status = parsed
chunk_count > 0
manufacturer = sungrow
product_series = SG
device_type = pv_inverter
document_type = sop
```

---

### 7.4 文档列表验收

```bash
curl "http://127.0.0.1:8000/api/knowledge/documents?manufacturer=huawei&device_type=pv_inverter"
```

必须能查到华为文档。

```bash
curl "http://127.0.0.1:8000/api/knowledge/documents?manufacturer=sungrow&device_type=pv_inverter"
```

必须能查到阳光文档。

---

### 7.5 切片查询验收

```bash
curl http://127.0.0.1:8000/api/knowledge/documents/{document_id}/chunks
```

必须满足：

```text
items 不为空
content 不为空
content 来自上传文档
chunk_index 连续
manufacturer / product_series / device_type 正确
```

---

### 7.6 数据库一致性验收

执行 SQL：

```sql
SELECT id, title, manufacturer, product_series, parse_status, chunk_count
FROM knowledge_documents
ORDER BY created_at DESC;

SELECT document_id, COUNT(*) AS actual_chunk_count
FROM knowledge_chunks
GROUP BY document_id;
```

必须满足：

```text
knowledge_documents.chunk_count = actual_chunk_count
```

---

### 7.7 异常上传验收

必须测试以下异常。

#### 空文件

预期：

```text
HTTP 400
message 明确说明文件为空
```

#### 不支持扩展名

上传 `.exe`、`.xlsx` 等文件。

预期：

```text
HTTP 415
message 明确说明不支持该类型
```

#### 扫描版或无法提取文本 PDF

预期：

```text
parse_status = failed
error_message 非空
不能生成空 chunks
```

---

## 8. 检索问答验收

### 8.1 华为绝缘阻抗低问答

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/retrieval/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "device_type": "pv_inverter",
    "top_k": 5
  }'
```

必须满足：

```text
answer 不为空
suggested_steps 不为空
references 不为空
retrieved_chunks 不为空
references[0].manufacturer = huawei
references[0].product_series = SUN2000
trace_id 存在
confidence > 0 且 < 1
qa_records 写入成功
```

---

### 8.2 阳光过温问答

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/retrieval/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "阳光 SG 系列逆变器过温降额怎么处理？",
    "manufacturer": "sungrow",
    "product_series": "SG",
    "device_type": "pv_inverter",
    "top_k": 5
  }'
```

必须满足：

```text
references 不为空
retrieved_chunks 不为空
answer 包含过温、散热、风扇或降额相关内容
qa_records 写入成功
```

---

### 8.3 无资料场景问答

请求一个知识库明显没有的问题，例如：

```text
摩托车发动机无法启动怎么处理？
```

预期：

```text
references = []
retrieved_chunks = []
confidence 较低
answer 提示当前知识库无足够资料
qa_records 仍写入
```

不得编造华为或阳光手册作为来源。

---

### 8.4 空问题验收

请求：

```json
{
  "query": "",
  "device_type": "pv_inverter"
}
```

预期：

```text
HTTP 400
message = query or question must not be empty
不写入 qa_records
```

---

### 8.5 top_k 超限验收

请求：

```json
{
  "query": "华为逆变器告警怎么处理？",
  "top_k": 20
}
```

预期：

```text
HTTP 400
message 明确说明 top_k 范围
```

---

### 8.6 qa_records 验收

查询：

```bash
curl http://127.0.0.1:8000/api/retrieval/records
```

必须能看到刚才问答记录。

SQL 验收：

```sql
SELECT trace_id, question, manufacturer, product_series, confidence, created_at
FROM qa_records
ORDER BY created_at DESC
LIMIT 5;
```

必须有记录。

---

## 9. 故障诊断验收

### 9.1 阳光过温诊断

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/diagnosis/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer": "sungrow",
    "product_series": "SG",
    "device_type": "pv_inverter",
    "fault_type": "over_temperature",
    "fault_description": "阳光 SG 系列逆变器中午高温时频繁出现过温降额，发电功率下降。",
    "include_references": true
  }'
```

必须满足：

```text
possible_causes 不为空
inspection_steps 不为空
safety_notes 不为空
recommended_actions 不为空
trace_id 存在
diagnosis_records 写入成功
```

---

### 9.2 华为通信中断诊断

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/diagnosis/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer": "huawei",
    "product_series": "FusionSolar",
    "device_type": "pv_inverter",
    "fault_type": "communication_interruption",
    "fault_description": "FusionSolar 平台显示逆变器离线，但现场设备可能仍在运行。",
    "include_references": true
  }'
```

必须满足：

```text
possible_causes 包含通信、采集器、网络或 RS485 相关内容
inspection_steps 不为空
safety_notes 不为空
diagnosis_records 写入成功
```

---

### 9.3 故障描述为空验收

请求：

```json
{
  "manufacturer": "huawei",
  "fault_description": ""
}
```

预期：

```text
HTTP 400 或 422
message 明确说明 fault_description 不能为空
不写入 diagnosis_records
```

---

### 9.4 diagnosis_records 验收

```bash
curl http://127.0.0.1:8000/api/diagnosis/records
```

SQL：

```sql
SELECT trace_id, manufacturer, product_series, fault_type, created_at
FROM diagnosis_records
ORDER BY created_at DESC
LIMIT 5;
```

必须能查到最近诊断记录。

---

## 10. 检修任务验收

### 10.1 创建任务

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/maintenance/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "处理华为 SUN2000 绝缘阻抗低告警",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "device_type": "pv_inverter",
    "fault_type": "low_insulation_resistance",
    "alarm_code": "LOW_INSULATION",
    "priority": "high",
    "assignee": "maintenance_engineer",
    "source_type": "qa",
    "source_trace_id": "qa_test_trace"
  }'
```

必须满足：

```text
maintenance_tasks 写入成功
task_status = pending
manufacturer = huawei
product_series = SUN2000
device_type = pv_inverter
```

---

### 10.2 查询任务列表

```bash
curl "http://127.0.0.1:8000/api/maintenance/tasks?manufacturer=huawei&task_status=pending"
```

必须能查到刚创建的任务。

---

### 10.3 更新任务状态

请求：

```bash
curl -X POST http://127.0.0.1:8000/api/maintenance/tasks/{task_id}/start \
  -H "Content-Type: application/json" \
  -d '{
    "task_status": "in_progress"
  }'
```

再更新完成：

```bash
curl -X POST http://127.0.0.1:8000/api/maintenance/tasks/{task_id}/complete \
  -H "Content-Type: application/json" \
  -d '{
    "task_status": "completed",
    "result_summary": "已完成现场排查，异常接插件处理后告警消除。",
    "completion_notes": "已复检并记录。"
  }'
```

必须满足：

```text
task_status 更新成功
completed_at 写入
result_summary 保存
```

---

### 10.4 非法状态流转验收

如任务已 completed，再尝试改回 pending。

预期：

```text
HTTP 409
message 明确说明状态不可流转
```

如当前后端未实现状态流转限制，应在后续任务中补充。

---

## 11. 记录追溯验收

### 11.1 问答记录追溯

前端和 API 必须能通过：

```text
trace_id
```

找到问答记录。

必须展示：

```text
question
answer
references
retrieved_chunks
suggested_steps
confidence
created_at
```

---

### 11.2 诊断记录追溯

必须展示：

```text
fault_description
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
created_at
```

---

### 11.3 任务来源追溯

如果任务有：

```text
source_trace_id
```

页面应提示该任务来源于问答或诊断。

第一版可不做自动跳转，但字段必须保存。

---

## 12. 前端页面验收

### 12.1 DashboardView

必须满足：

```text
1. 页面文案聚焦华为/阳光电源光伏逆变器
2. 不出现泛新能源设备主线
3. 能调用 /api/system/status
4. 能显示文档数、切片数、问答数、诊断数、任务数
5. 数据库异常时显示错误提示
```

---

### 12.2 KnowledgeBaseView

必须满足：

```text
1. 能选择厂家：华为 / 阳光电源
2. 能选择产品系列：SUN2000 / FusionSolar / SG
3. 设备类型默认光伏逆变器
4. 能上传 txt/md/pdf/docx
5. 上传成功后刷新列表
6. 能查看真实 chunks
7. 上传失败显示真实错误
```

---

### 12.3 RetrievalChatView

必须满足：

```text
1. 能输入问题
2. 能选择 manufacturer/product_series
3. 能展示 answer
4. 能展示 suggested_steps
5. 能展示 references
6. 能展示 retrieved_chunks
7. 能展示 trace_id
8. 无 references 时不编造来源
```

---

### 12.4 FaultDiagnosisView

必须满足：

```text
1. 能输入 fault_description
2. 能选择 fault_type
3. 能展示 possible_causes
4. 能展示 inspection_steps
5. 能突出展示 safety_notes
6. 能展示 recommended_actions
7. 能展示 trace_id
```

---

### 12.5 MaintenanceTaskView

必须满足：

```text
1. 能创建任务
2. 能查询任务列表
3. 能按状态、厂家筛选
4. 能查看任务详情
5. 能更新任务状态
6. 刷新后数据不丢失
```

---

### 12.6 RecordCenterView

必须满足：

```text
1. 能查看 qa_records
2. 能查看 diagnosis_records
3. 能查看 trace_id
4. 能查看 references
5. 能查看 retrieved_chunks 或诊断步骤
```

---

### 12.7 SystemStatusView

必须满足：

```text
1. 能展示后端状态
2. 能展示数据库状态
3. 能展示部署目标 LoongArch + Kylin
4. 数据库断开时不能显示 connected
```

---

## 13. 部署验收

部署验收遵循：

```text
08_deployment_and_loongarch_kylin_spec.md
```

核心命令：

```bash
systemctl status postgresql
systemctl status energy-maintenance-backend
systemctl status nginx
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/system/status
curl http://服务器IP/api/health
```

必须满足：

```text
PostgreSQL active
后端 active
Nginx active
前端可访问
/api 可访问
数据库 connected
```

---

## 14. 质量门禁

每次 Codex 完成开发任务后，必须输出以下内容。

### 14.1 修改文件清单

```text
Modified files:
- backend/app/...
- frontend/src/...
- docs/...
```

---

### 14.2 执行命令清单

必须说明真实执行了哪些命令：

```text
Executed:
- python -m compileall app
- alembic -c alembic.ini upgrade head
- npm run build
- curl ...
```

未执行的命令必须明确说明：

```text
Not executed:
- alembic upgrade head，因为当前 PostgreSQL 未启动
```

不得把未执行命令写成已通过。

---

### 14.3 验收结果清单

应按功能列出：

```text
Database migration: passed / failed / not executed
Knowledge upload: passed / failed / not executed
Retrieval QA: passed / failed / not executed
Fault diagnosis: passed / failed / not executed
Task management: passed / failed / not executed
Frontend build: passed / failed / not executed
```

---

### 14.4 未完成项

必须明确列出：

```text
Known issues:
1. PostgreSQL 未连接，因此真实入库未验收
2. 前端未实现 RecordCenterView
3. references 暂未展示 page_number
```

不得省略关键问题。

---

## 15. 回归测试要求

每次修改以下模块后必须回归对应功能。

### 15.1 修改数据库模型后

必须回归：

```text
Alembic migration
knowledge upload
retrieval query
records query
```

---

### 15.2 修改知识库处理后

必须回归：

```text
txt 上传
md 上传
pdf 上传
docx 上传
chunks 查询
检索问答
```

---

### 15.3 修改检索问答后

必须回归：

```text
华为绝缘阻抗低问答
阳光过温问答
无资料问题
qa_records 查询
```

---

### 15.4 修改故障诊断后

必须回归：

```text
过温诊断
通信中断诊断
绝缘阻抗低诊断
diagnosis_records 查询
```

---

### 15.5 修改前端 API 封装后

必须回归：

```text
知识库列表
文档上传
问答提交
诊断提交
任务创建
记录追溯
```

---

## 16. 不通过判定标准

出现以下任一情况，不能判定为第一版完成：

```text
1. PostgreSQL 未真实连接
2. Alembic 未真实执行
3. knowledge_chunks 没有真实内容
4. /api/retrieval/query 不返回真实 references
5. qa_records 未写入
6. diagnosis_records 未写入
7. maintenance_tasks 未写入
8. 前端展示大量假数据
9. 系统范围扩散到泛新能源设备
10. 正式部署仍依赖 Docker
```

---

## 17. 验收报告模板

每次阶段验收建议使用以下模板。

```text
# Energy-Maintenance 阶段验收报告

## 1. 验收范围
本次验收内容：

## 2. 环境信息
- OS:
- Python:
- Node:
- PostgreSQL:
- Backend:
- Frontend:

## 3. 执行命令
- ...

## 4. 数据库迁移结果
- passed / failed
- 说明：

## 5. 功能验收结果
### 5.1 知识库上传
- passed / failed
- 证据：

### 5.2 检索问答
- passed / failed
- 证据：

### 5.3 故障诊断
- passed / failed
- 证据：

### 5.4 检修任务
- passed / failed
- 证据：

### 5.5 前端页面
- passed / failed
- 证据：

## 6. 未完成问题
1. ...

## 7. 下一步修正任务
1. ...
```

---

## 18. 与其他文档关系

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
```

其中：

- `01` 确定产品范围；
- `02` 确定技术架构；
- `03` 确定数据库结构；
- `04` 确定 API 契约；
- `05` 确定前端交互；
- `06` 确定知识库处理；
- `07` 确定检索问答和故障诊断；
- `08` 确定部署方案；
- `09` 确定测试、验收和质量门禁。

---

## 19. 下一步建议

本文档确认后，下一份建议编写：

```text
10_vibe_coding_task_plan.md
```

下一份文档应将后续开发拆成可执行的小任务，每个任务明确：

```text
目标
允许修改文件
禁止事项
执行命令
验收标准
完成输出
```

该文档将直接用于指导 Codex 逐步开发，避免一次性大范围修改导致系统跑偏。
---

## Task 02A 验收口径补充

本补充用于区分静态文档审查、代码静态检查和真实闭环验收。

### A. Task 02A 验收边界

Task 02A 只进行文档和静态一致性审查，不执行：

- PostgreSQL 真实连接。
- `alembic upgrade head`。
- 真实写入数据库。
- 新增业务接口。
- 新增前端页面。

### B. 后续真实验收必须执行

进入数据库实现和闭环验收任务后，必须真实执行：

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

并完成：

- 样例文档上传。
- knowledge_documents 写入。
- knowledge_chunks 生成。
- retrieval query 返回真实 references。
- qa_records 写入并可查询。
- diagnosis_records 写入并可查询。
- maintenance_tasks 创建和状态更新。

### C. 不可替代真实验收的证据

以下结果只能作为辅助证据，不能替代真实闭环验收：

- 静态代码阅读。
- 离线 SQL 生成。
- 前端静态构建。
- 文档补充完成。
- 接口设计完成。

如数据库未启动，必须明确标注为未执行，不得写成通过。

---

## Task 14A 补充：全局 Smoke 与交付边界检查

Task 14A 增加以下轻量验收脚本，用于部署前和演示前快速发现环境、数据和路由问题。

### A. PostgreSQL 检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_postgresql.ps1
```

检查内容：

```text
1. D:\Work Space\PostgreSQL\bin\psql.exe 或 PATH 中 psql 是否可用
2. pg_isready 是否可用
3. Windows PostgreSQL 服务状态和启动类型
4. 127.0.0.1:5432 是否可达
5. energy_user 是否可连接 energy_maintenance
```

该脚本不修改服务启动类型，不创建数据库，不使用 Docker。

### B. 演示数据审计

```powershell
cd backend
uv run python scripts/demo_data_audit.py
```

该脚本只读统计：

```text
test users
Task11A_Disposable documents
demo devices
demo knowledge
demo SOP
demo tasks
corrections
suspicious QA records
```

脚本不执行 DELETE，不自动归档数据。

### C. 核心 API Smoke

```powershell
cd backend
uv run python scripts/full_smoke_check.py
```

前置条件：

```text
1. PostgreSQL 可连接
2. 后端运行在 http://127.0.0.1:8000
3. admin 账号可登录
```

检查接口：

```text
GET  /api/health
GET  /api/system/status
GET  /api/system/statistics
GET  /api/devices
GET  /api/knowledge/documents
POST /api/retrieval/query
POST /api/diagnosis/analyze
POST /api/sop/generate
GET  /api/maintenance/tasks
GET  /api/record-center/overview
GET  /api/model-gateway/status
```

说明：`retrieval/query` 和 `diagnosis/analyze` 会写入带 `Task14A_Smoke` 标识的追溯记录；脚本不删除数据。

### D. 前端路由 Smoke

```powershell
powershell -ExecutionPolicy Bypass -File scripts/frontend_route_smoke.ps1
```

检查页面路由是否返回 Vite app shell：

```text
/login
/dashboard
/status
/devices
/knowledge
/retrieval
/diagnosis
/sop
/tasks
/records
/review
/model-service
```

该脚本不执行浏览器点击自动化，不替代最终人工演示验收。

### E. 文件边界

交付前必须确认：

```text
backend/.env 不提交
frontend/dist 不提交
backend/storage/uploads 运行文件不提交
backend/storage/uploads/**/.gitkeep 可保留
node_modules 不提交
.venv 不提交
Dockerfile / docker-compose.yml 不存在
```

---

## Task 14B Cloud Model Integration Acceptance

Task 14B must not execute `alembic upgrade head`, create migrations, or add Docker files.

Required static checks:

```powershell
cd backend
uv run python -m compileall app
uv run python -m alembic -c alembic.ini current

cd ../frontend
npm.cmd run type-check
npm.cmd run build
```

Required runtime check after backend startup:

```powershell
cd backend
uv run python scripts/check_cloud_model_flow.py
```

Acceptance interpretation:

- If `CLOUD_LLM_*` is incomplete, real cloud integration is `blocked`, not passed.
- In blocked mode, Model Gateway and business endpoints must use safe `rule_based` fallback when fallback is allowed.
- If `CLOUD_LLM_*` is complete, the script must verify real `cloud_openai` calls and `model_call_logs` traceability.
- `CLOUD_LLM_API_KEY` must not appear in frontend responses, log list/detail responses, command output, or reports.

---

## Task 18D Knowledge Graph Business Integration Acceptance

Task 18D must not create an Alembic revision, execute `alembic upgrade head`, introduce Docker, introduce SQLite, or add external graph/vector/model dependencies.

Required static checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current

cd ..\frontend
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
```

Expected Alembic current:

```text
20260601_0003 (head)
```

Required runtime checks after backend startup:

```powershell
cd backend
uv run python scripts/seed_demo_knowledge_graph.py
uv run python scripts/check_knowledge_graph_flow.py
uv run python scripts/check_kg_business_integration.py

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
```

Acceptance criteria:

- `/api/kg/overview`, `/api/kg/graph`, `/api/kg/search`, `/api/kg/business-context`, `/api/kg/neighborhood/{node_id}`, and `/api/kg/path` return real PostgreSQL graph data when seeded graph data exists.
- `POST /api/retrieval/query` with `enable_kg_enhancement=true` may return graph context, evidence, paths, nodes, and edges when relevant active graph data exists.
- `POST /api/diagnosis/analyze` with `enable_kg_enhancement=true` may return graph-related causes, inspection items, actions, safety risks, and evidence.
- `POST /api/sop/generate` with `enable_kg_enhancement=true` may return graph-related tools, parts, safety risks, steps, and evidence.
- `GET /api/record-center/records/{record_type}/{record_id}` may expose saved graph context and evidence summaries.
- Viewer can read graph data but cannot create graph nodes, graph edges, evidence, or approve candidates.
- No graph fact, reference, path, node, edge, or evidence item may be fabricated by frontend code or model output.

Known deferred checks:

- Manual browser inspection remains recommended for graph canvas readability and role-specific button visibility.
- Real model-based graph extraction, OCR, embedding, pgvector, and external graph database checks are out of scope.

---

## Task 18E Cloud Model Online Acceptance

Task 18E verifies the optional `cloud_openai` OpenAI-compatible provider. It must not execute `alembic upgrade head`, create migrations, introduce Docker, introduce SQLite, introduce pgvector/embedding, or enable OCR.

Required static checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current

cd ..\frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
```

Expected Alembic current:

```text
20260601_0003 (head)
```

Runtime checks after backend startup:

```powershell
cd D:\Work Space\Energy-Maintenance
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1

cd backend
uv run python scripts\check_cloud_model_online.py
```

`check_cloud_model_online.py` must report one of:

- `passed`: real cloud credentials are configured and all cloud calls pass without fallback.
- `blocked`: `CLOUD_LLM_*` is missing or disabled; fallback is verified and no real cloud success is claimed.
- `failed`: credentials are present but provider call, business enhancement, logging, or secret-safety checks fail.

Acceptance criteria when credentials are configured:

- `cloud_openai` test call succeeds.
- `cloud_openai` chat call succeeds.
- retrieval, diagnosis, and SOP model enhancement use `cloud_openai` without fallback.
- Model Gateway status can report `cloud_openai` as `available` after a real successful call.
- `model_call_logs` contain provider, model, latency, success/error, prompt, response, and token usage where available.
- `model_call_logs`, status responses, and frontend responses do not expose `CLOUD_LLM_API_KEY` or Authorization headers.
- KG context and media metadata are included only as safe prompt summaries.

Acceptance criteria when credentials are absent:

- real cloud call is `blocked`, not `passed`.
- rule-based fallback remains available.
- final smoke and build checks still pass.
# Task 18F Local llama.cpp / GGUF Acceptance

Task 18F prepares optional local llama.cpp / GGUF integration. It must not download models, install llama.cpp, execute `alembic upgrade head`, create migrations, introduce Docker, introduce SQLite, or introduce pgvector/embedding/OCR.

Required static checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current

cd ..\frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
```

Expected Alembic current:

```text
20260601_0003 (head)
```

Runtime checks after backend startup:

```powershell
cd D:\Work Space\Energy-Maintenance
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1

cd backend
uv run python scripts\check_local_llama_cpp_flow.py
```

Acceptance modes:

- `passed`: local llama.cpp is enabled, reachable, and real local calls succeed.
- `blocked`: local llama.cpp is disabled or unreachable; rule-based fallback is verified.
- `failed`: local llama.cpp is configured but calls, logs, or safety checks fail.

The blocked mode is acceptable when no local llama.cpp server is running, but it must not be reported as real local model success.

# Task 18G Optional OCR Acceptance

Task 18G validates an optional OCR workflow. It must not install Tesseract, download language packs, execute `alembic upgrade head`, create migrations, introduce Docker, introduce SQLite, or introduce pgvector/embedding/deep-learning OCR dependencies.

Required static checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current

cd ..\frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
```

Expected Alembic current:

```text
20260601_0003 (head)
```

Runtime checks after backend startup:

```powershell
cd D:\Work Space\Energy-Maintenance
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1

cd backend
uv run python scripts\check_ocr_flow.py

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\check_tesseract_env.ps1
```

Acceptance modes:

- `passed`: OCR is enabled, Tesseract is available, image OCR processing succeeds, and retrieval/diagnosis can include processed OCR text when requested.
- `blocked`: OCR is disabled or Tesseract/language data is missing; the application remains healthy and no real OCR success is claimed.
- `failed`: OCR is configured but status, permission, processing, logging, or safety checks fail.

Additional acceptance rules:

- viewer users must not trigger OCR processing;
- OCR text must be labeled as machine-recognized reference text;
- OCR must not be presented as image fault recognition or visual understanding;
- references must still come from real approved `knowledge_chunks`.

# Task 18H Final Freeze Acceptance

Task 18H is the final delivery-freeze validation task. It must not add business features, create Alembic migrations, introduce Docker, introduce SQLite, introduce pgvector/embedding, download model files, install OCR engines, or commit secrets.

Windows final checks:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current

cd ..\frontend
npm.cmd install
npm.cmd audit
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
```

Special checks:

```powershell
cd backend
uv run python scripts\check_knowledge_graph_flow.py
uv run python scripts\check_kg_business_integration.py
uv run python scripts\check_cloud_model_online.py
uv run python scripts\check_local_llama_cpp_flow.py
uv run python scripts\check_ocr_flow.py
```

Linux/Kylin smoke:

```bash
API_BASE_URL=http://127.0.0.1:8000 bash scripts/final_smoke_test.sh
```

Acceptance interpretation:

- Windows final regression may be `passed`.
- cloud model, local llama.cpp, and OCR may be `blocked` if they are not configured; this is acceptable when reported honestly.
- LoongArch/Kylin real acceptance is `blocked` until a real target host executes `check_loongarch_kylin.sh`, database migration, backend startup, and `final_smoke_test.sh`.
- New target databases may run `alembic upgrade head`; the Windows validation database should only use `alembic current` during freeze unless an explicit migration task starts.

# Task 18I Global Acceptance Regression

Task 18I adds one end-to-end HTTP acceptance script for the completed first-version feature set:

```powershell
cd backend
uv run python scripts\check_global_acceptance.py
```

The script must:

- create only `Task18I_`-prefixed temporary test data;
- verify auth/RBAC, devices, maintenance records, media, knowledge contributions, knowledge documents/chunks, retrieval, diagnosis, SOP, maintenance tasks, record center, corrections, KG, model gateway, system status, and SPA fallback routes;
- save retrieval and diagnosis traces to PostgreSQL-backed records;
- treat cloud model, local llama.cpp, and OCR as `blocked` when they are disabled or unconfigured;
- soft-archive or disable safe Task18I data at the end;
- exit with code 0 only when core business checks have no `failed` items.

Task 18I must not execute `alembic upgrade head`, create migrations, introduce Docker, introduce SQLite, introduce pgvector/embedding, download models, install OCR engines, or claim blocked external capabilities as passed.
