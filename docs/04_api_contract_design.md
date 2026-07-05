# 04 API 接口契约设计文档

**Document Name:** `04_api_contract_design.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Backend:** FastAPI  
**Database:** PostgreSQL  
**API Prefix:** `/api`  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版后端 API 接口契约，作为后续前端开发、后端开发、数据库联调、接口测试和 vibe coding 的统一依据。

本项目第一版范围已明确为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

因此，所有 API 设计必须服务于以下核心业务闭环：

```text
上传华为 / 阳光电源逆变器资料
    ↓
文档解析与知识切片入库
    ↓
检索真实 knowledge_chunks
    ↓
生成可追溯检修回答
    ↓
保存 qa_records
    ↓
进行故障辅助诊断
    ↓
创建检修任务
    ↓
形成记录追溯
```

本文档重点解决以下问题：

```text
1. API 路径不能随意变化
2. 请求和响应字段不能前后端不一致
3. references 必须来自真实知识库切片
4. 问答、诊断、任务必须真实写入 PostgreSQL
5. 错误响应必须统一
6. 后续 Codex 开发必须按契约执行
```

---

## 2. API 总体设计原则

### 2.1 对外路径统一使用 `/api`

第一版对外接口统一使用：

```text
/api/...
```

允许后端内部目录使用：

```text
backend/app/api/routes/
```

但对外暴露路径不得变成：

```text
public versioned API prefix
```

除非未来明确进行版本化改造，并同步修改前端、README 和 API 文档。

---

### 2.2 API 层不得直接操作数据库

后端分层调用必须遵循：

```text
api -> service -> repository -> model
```

API 层职责：

```text
1. 接收请求
2. 校验参数
3. 调用 service
4. 返回统一响应
```

API 层禁止：

```text
1. 直接写 SQL
2. 直接操作 SQLAlchemy session 进行复杂业务
3. 直接解析文件内容
4. 直接构造 RAG 检索逻辑
5. 直接伪造 references
```

---

### 2.3 所有接口必须返回统一响应结构

成功响应统一格式：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

失败响应统一格式：

```json
{
  "code": 400,
  "message": "Invalid request",
  "data": null,
  "trace_id": "optional-trace-id"
}
```

说明：

- `code` 使用业务状态码，与 HTTP 状态码保持大体一致；
- `message` 提供可读错误信息；
- `data` 成功时为对象、数组或分页对象，失败时可为 `null`；
- `trace_id` 可选，用于问题追踪。

---

### 2.4 所有写入型接口必须真实写入 PostgreSQL

以下接口不能只做内存模拟：

```text
POST /api/knowledge/documents/upload
POST /api/retrieval/query
POST /api/diagnosis/analyze
POST /api/maintenance/tasks
POST /api/maintenance/tasks/{task_id}/start
POST /api/maintenance/tasks/{task_id}/complete
POST /api/maintenance/tasks/{task_id}/cancel
```

必须写入或更新对应 PostgreSQL 表：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

---

### 2.5 第一版厂家与设备范围必须固定

所有相关接口涉及厂家、设备类型、产品系列时，应遵守以下枚举基线。

#### manufacturer

```text
huawei
sungrow
```

#### product_series

```text
SUN2000
FusionSolar
SG
```

#### device_type

```text
pv_inverter
```

第一版不应在前端主动暴露以下设备类型：

```text
battery
energy_storage
transformer
box_transformer
power_inspection_device
generic_renewable_equipment
```

---

## 3. 通用分页结构

列表接口统一支持分页。

### 3.1 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| page | integer | 否 | 1 | 页码，从 1 开始 |
| page_size | integer | 否 | 10 | 每页数量 |
| keyword | string | 否 | null | 搜索关键词 |

### 3.2 分页响应结构

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 10
}
```

### 3.3 分页限制

建议限制：

```text
1 <= page
1 <= page_size <= 100
```

超过限制应返回 400。

---

## 4. 通用错误码

| HTTP 状态码 | code | 场景 | 说明 |
|---:|---:|---|---|
| 200 | 200 | 成功 | 请求成功 |
| 201 | 201 | 创建成功 | 可选，第一版也可统一 200 |
| 400 | 400 | 参数错误 | 缺少字段、枚举非法、空问题 |
| 401 | 401 | 未认证 | 后续权限系统使用 |
| 403 | 403 | 无权限 | 后续权限系统使用 |
| 404 | 404 | 资源不存在 | 文档、任务、记录不存在 |
| 409 | 409 | 状态冲突 | 重复创建、状态不可流转 |
| 413 | 413 | 文件过大 | 上传文件超过限制 |
| 415 | 415 | 文件类型不支持 | 不支持的文件扩展名 |
| 422 | 422 | FastAPI 参数校验失败 | 请求体结构不合法 |
| 500 | 500 | 服务器内部错误 | 未捕获异常 |
| 503 | 503 | 服务不可用 | 数据库、大模型或外部服务不可用 |

---

## 5. Health 与系统信息接口

---

# 5.1 健康检查

## 接口

```http
GET /api/health
```

## 说明

用于检查后端服务是否运行。

## 请求参数

无。

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "name": "Energy-Maintenance",
    "status": "running",
    "version": "0.1.0",
    "environment": "development",
    "time": "2026-05-27T12:00:00+08:00"
  }
}
```

## 验收标准

```text
1. 后端启动后接口可访问
2. status = running
3. name = Energy-Maintenance
4. 不依赖数据库也应能返回基础运行状态
```

---

# 5.2 系统信息

## 接口

```http
GET /api/system/info
```

## 说明

返回系统定位、技术栈、业务范围、当前版本等信息。

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "name": "Energy-Maintenance",
    "description": "面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统",
    "version": "0.1.0",
    "backend": "FastAPI",
    "frontend": "Vue3 + Vite + TypeScript",
    "database": "PostgreSQL",
    "deployment_target": "LoongArch + Kylin",
    "supported_manufacturers": ["huawei", "sungrow"],
    "supported_device_types": ["pv_inverter"]
  }
}
```

## 验收标准

```text
1. 系统描述不得再泛化为所有新能源设备
2. supported_manufacturers 仅包含 huawei / sungrow
3. supported_device_types 第一版仅包含 pv_inverter
```

---

# 5.3 系统状态

## 接口

```http
GET /api/system/status
```

## 说明

用于系统状态页展示后端、数据库、知识库统计等状态。

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "service_status": "running",
    "database_status": "connected",
    "document_count": 12,
    "chunk_count": 358,
    "qa_record_count": 45,
    "diagnosis_record_count": 16,
    "maintenance_task_count": 8
  }
}
```

## 验收标准

```text
1. database_status 必须真实检查数据库连接
2. 统计数据来自 PostgreSQL
3. 数据库不可用时不能假装 connected
```

---

## 6. 知识库接口

知识库接口用于管理华为和阳光电源光伏逆变器相关文档，包括上传、解析、切片、列表、详情、切片查看等能力。

---

# 6.1 上传并解析文档

## 接口

```http
POST /api/knowledge/documents/upload
```

## Content-Type

```text
multipart/form-data
```

## 说明

上传文档并执行：

```text
保存文件
    ↓
解析文本
    ↓
清洗文本
    ↓
文本切片
    ↓
写入 knowledge_documents
    ↓
写入 knowledge_chunks
```

## 表单字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| file | file | 是 | 上传文件 |
| title | string | 否 | 文档标题，不填则使用文件名 |
| manufacturer | string | 是 | huawei / sungrow |
| product_series | string | 否 | SUN2000 / FusionSolar / SG |
| model | string | 否 | 具体型号 |
| device_type | string | 是 | 第一版固定 pv_inverter |
| document_type | string | 是 | manual / alarm_code / sop / fault_case / inspection_standard / maintenance_record |
| source | string | 否 | 来源，如 official_manual / local_sample / user_upload |
| summary | string | 否 | 摘要 |

## 支持文件类型

```text
.txt
.md
.pdf
.docx
```

第一版说明：

```text
1. txt/md 必须真实解析
2. pdf 支持文本型 PDF，不做扫描版 OCR
3. docx 支持段落和表格文本提取
4. 不支持文件类型应返回 415
5. 空文件应返回 400
```

## 请求示例 curl

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@sample_huawei_sun2000_alarm.txt" \
  -F "title=华为 SUN2000 逆变器告警排查样例" \
  -F "manufacturer=huawei" \
  -F "product_series=SUN2000" \
  -F "device_type=pv_inverter" \
  -F "document_type=alarm_code" \
  -F "source=local_sample"
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "document": {
      "id": "doc-001",
      "title": "华为 SUN2000 逆变器告警排查样例",
      "manufacturer": "huawei",
      "product_series": "SUN2000",
      "device_type": "pv_inverter",
      "document_type": "alarm_code",
      "file_name": "sample_huawei_sun2000_alarm.txt",
      "file_ext": "txt",
      "file_size": 12560,
      "parse_status": "parsed",
      "chunk_count": 8,
      "created_at": "2026-05-27T12:00:00+08:00"
    },
    "chunk_count": 8,
    "parse_status": "parsed",
    "warnings": []
  }
}
```

## 失败响应示例：不支持文件类型

```json
{
  "code": 415,
  "message": "Unsupported document extension: exe",
  "data": null
}
```

## 失败响应示例：解析失败

```json
{
  "code": 400,
  "message": "Document parsing failed: extracted text is empty",
  "data": {
    "parse_status": "failed",
    "error_message": "extracted text is empty"
  }
}
```

## 数据库写入要求

成功时必须写入：

```text
knowledge_documents
knowledge_chunks
```

并满足：

```text
knowledge_documents.parse_status = parsed
knowledge_documents.chunk_count = COUNT(knowledge_chunks where document_id = id)
knowledge_chunks.content 不为空
knowledge_chunks.manufacturer 与 document 一致
knowledge_chunks.device_type = pv_inverter
```

## 验收标准

```text
1. 上传华为样例文档成功
2. 上传阳光电源样例文档成功
3. parse_status = parsed
4. chunk_count > 0
5. knowledge_chunks 中有真实文本内容
6. 不支持类型返回明确错误
7. 空文件返回明确错误
8. 文件不得保存到 frontend 目录
```

---

# 6.2 查询文档列表

## 接口

```http
GET /api/knowledge/documents
```

## 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| keyword | string | 否 | null | 标题关键词 |
| manufacturer | string | 否 | null | huawei / sungrow |
| product_series | string | 否 | null | SUN2000 / FusionSolar / SG |
| device_type | string | 否 | pv_inverter | 设备类型 |
| document_type | string | 否 | null | 文档类型 |
| parse_status | string | 否 | null | pending / processing / parsed / failed |
| status | string | 否 | active | 文档状态 |

## 请求示例

```http
GET /api/knowledge/documents?manufacturer=huawei&device_type=pv_inverter&parse_status=parsed&page=1&page_size=10
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "doc-001",
        "title": "华为 SUN2000 逆变器告警排查样例",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "document_type": "alarm_code",
        "file_name": "sample_huawei_sun2000_alarm.txt",
        "file_size": 12560,
        "parse_status": "parsed",
        "chunk_count": 8,
        "created_at": "2026-05-27T12:00:00+08:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

## 验收标准

```text
1. 支持 manufacturer 过滤
2. 支持 product_series 过滤
3. 支持 document_type 过滤
4. 支持 parse_status 过滤
5. 返回分页结构
6. 列表数据来自 PostgreSQL
```

---

# 6.3 查询文档详情

## 接口

```http
GET /api/knowledge/documents/{document_id}
```

## 路径参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| document_id | string / integer | 是 | 文档 ID |

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "doc-001",
    "title": "华为 SUN2000 逆变器告警排查样例",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "model": "SUN2000",
    "device_type": "pv_inverter",
    "document_type": "alarm_code",
    "source": "local_sample",
    "file_name": "sample_huawei_sun2000_alarm.txt",
    "file_path": "storage/uploads/2026/05/sample_huawei_sun2000_alarm.txt",
    "file_size": 12560,
    "file_ext": "txt",
    "page_count": null,
    "parse_status": "parsed",
    "parser_name": "text_parser",
    "chunk_count": 8,
    "summary": "华为 SUN2000 逆变器告警排查样例资料",
    "error_message": null,
    "metadata_json": {},
    "parsed_at": "2026-05-27T12:00:00+08:00",
    "created_at": "2026-05-27T12:00:00+08:00",
    "updated_at": "2026-05-27T12:00:00+08:00"
  }
}
```

## 404 响应示例

```json
{
  "code": 404,
  "message": "Knowledge document not found",
  "data": null
}
```

---

# 6.4 查询文档切片

## 接口

```http
GET /api/knowledge/documents/{document_id}/chunks
```

## 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| keyword | string | 否 | null | 切片内容关键词 |

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "chunk-001",
        "document_id": "doc-001",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "document_type": "alarm_code",
        "chunk_index": 0,
        "section_title": "绝缘阻抗低告警处理",
        "content": "当 SUN2000 逆变器出现绝缘阻抗低告警时，应首先检查直流侧组串、电缆绝缘和接地情况...",
        "char_count": 356,
        "page_number": 12,
        "embedding_status": "pending",
        "created_at": "2026-05-27T12:00:00+08:00"
      }
    ],
    "total": 8,
    "page": 1,
    "page_size": 10
  }
}
```

## 验收标准

```text
1. 返回真实 knowledge_chunks
2. content 不为空
3. chunk_index 正确
4. manufacturer / product_series / device_type 与文档一致
5. document_id 不存在时返回 404
```

---

# 6.5 删除文档

## 接口

```http
DELETE /api/knowledge/documents/{document_id}
```

## 说明

第一版建议使用软删除，将文档 `status` 设置为 `inactive`，并同步将关联 chunks 设置为 `inactive`。

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "document_id": "doc-001",
    "status": "inactive",
    "deleted_chunks": 8
  }
}
```

## 验收标准

```text
1. 删除后文档不再参与检索
2. 删除后 chunks 不再参与检索
3. 不应物理删除上传文件，除非明确实现文件清理
```

---

# 6.6 重新解析文档

## 接口

```http
POST /api/knowledge/documents/{document_id}/reparse
```

## 说明

用于对已上传文件重新执行解析、清洗、切片。

第一版可同步执行，后续可改为异步任务。

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "document_id": "doc-001",
    "parse_status": "parsed",
    "chunk_count": 9,
    "warnings": []
  }
}
```

## 验收标准

```text
1. 重新解析前应删除或置 inactive 旧 chunks
2. 重新解析后 chunk_count 与新 chunks 数量一致
3. 解析失败时 parse_status = failed
```

---

## 7. 检修知识问答接口

---

# 7.1 检索问答

## 接口

```http
POST /api/retrieval/query
```

## 说明

基于 `knowledge_chunks` 执行检索，生成可追溯的检修问答结果，并保存到 `qa_records`。

第一版使用关键词检索和规则型回答生成；后续可升级为 pgvector、embedding 和大模型生成。

## 请求体字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| query | string | 否 | null | 用户问题 |
| question | string | 否 | null | 兼容旧字段，与 query 至少一个非空 |
| manufacturer | string | 否 | null | huawei / sungrow |
| product_series | string | 否 | null | SUN2000 / FusionSolar / SG |
| device_type | string | 否 | pv_inverter | 第一版固定光伏逆变器 |
| document_type | string | 否 | null | 文档类型过滤 |
| top_k | integer | 否 | 5 | 返回切片数量，最大 10 |
| include_sources | boolean | 否 | true | 是否返回 references |

## 请求示例

```json
{
  "query": "华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？",
  "manufacturer": "huawei",
  "product_series": "SUN2000",
  "device_type": "pv_inverter",
  "document_type": "alarm_code",
  "top_k": 5,
  "include_sources": true
}
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "answer": "根据已入库的华为 SUN2000 光伏逆变器资料，系统检索到与绝缘阻抗低相关的告警排查内容。建议先确认告警发生时间和组串范围，再检查直流侧组串、电缆绝缘、接地状态和组件受潮情况；完成现场检查后，应复位告警并观察是否再次触发。",
    "suggested_steps": [
      "确认现场具备安全检修条件，必要时按规程停机或隔离直流侧。",
      "在监控平台或设备本地界面查看告警代码、发生时间和关联组串。",
      "检查直流侧组串、电缆、接插件和接地情况。",
      "使用合规仪表检测绝缘阻抗，判断是否存在受潮、破损或接地异常。",
      "处理异常点后恢复运行，观察告警是否消除。",
      "记录处理过程、检测结果和复检结论。"
    ],
    "references": [
      {
        "document_id": "doc-001",
        "document_title": "华为 SUN2000 逆变器告警排查样例",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "document_type": "alarm_code",
        "device_type": "pv_inverter",
        "section_title": "绝缘阻抗低告警处理",
        "chunk_index": 0,
        "page_number": 12,
        "source": "local_sample",
        "score": 0.82
      }
    ],
    "retrieved_chunks": [
      {
        "chunk_id": "chunk-001",
        "document_id": "doc-001",
        "document_title": "华为 SUN2000 逆变器告警排查样例",
        "section_title": "绝缘阻抗低告警处理",
        "content": "当 SUN2000 逆变器出现绝缘阻抗低告警时，应首先检查直流侧组串、电缆绝缘和接地情况...",
        "score": 0.82
      }
    ],
    "confidence": 0.78,
    "trace_id": "qa_20260527_001",
    "query_analysis": {
      "normalized_query": "华为 SUN2000 逆变器 绝缘阻抗低 排查",
      "matched_terms": ["华为", "SUN2000", "逆变器", "绝缘阻抗低", "排查"]
    }
  }
}
```

## 无检索结果响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "answer": "当前知识库中未检索到足够相关的华为或阳光电源光伏逆变器资料。以下仅提供通用安全排查建议：请先确认设备状态、告警信息和现场安全条件，再依据厂家手册进行处理。",
    "suggested_steps": [
      "确认现场安全条件，避免带电误操作。",
      "记录设备厂家、产品系列、型号、告警代码和故障现象。",
      "补充上传对应厂家设备手册、告警代码表或检修规程。",
      "在资料入库后重新发起检修问答。"
    ],
    "references": [],
    "retrieved_chunks": [],
    "confidence": 0.2,
    "trace_id": "qa_20260527_002",
    "query_analysis": {
      "normalized_query": "未知问题",
      "matched_terms": []
    }
  }
}
```

## 参数错误示例：空问题

```json
{
  "code": 400,
  "message": "query or question must not be empty",
  "data": null
}
```

## 参数错误示例：top_k 超限

```json
{
  "code": 400,
  "message": "top_k must be between 1 and 10",
  "data": null
}
```

## 数据库写入要求

每次调用该接口必须写入 `qa_records`：

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
```

## 重要约束

```text
1. references 必须来自真实 knowledge_chunks
2. 无检索结果时 references 必须为空数组
3. 不得编造文档标题、页码、来源
4. confidence 不得为 1.0
5. qa_records 必须真实入库
```

## 验收标准

```text
1. 上传华为样例文档后，华为问题能检索到真实 chunks
2. 上传阳光样例文档后，阳光问题能检索到真实 chunks
3. references 不为空且来自真实文档
4. retrieved_chunks 不为空
5. qa_records 中能查到本次问答
6. trace_id 一致
```

---

## 8. 故障辅助诊断接口

---

# 8.1 逆变器故障诊断

## 接口

```http
POST /api/diagnosis/analyze
```

## 说明

根据用户输入的厂家、产品系列、故障类型、告警代码、故障描述等信息，生成初步故障原因、排查步骤、安全注意事项和推荐处理措施，并保存到 `diagnosis_records`。

第一版可使用规则型诊断逻辑，后续可结合知识库检索和大模型增强。

## 请求体字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| manufacturer | string | 否 | null | huawei / sungrow |
| product_series | string | 否 | null | SUN2000 / FusionSolar / SG |
| device_type | string | 否 | pv_inverter | 光伏逆变器 |
| device_name | string | 否 | null | 设备名称 |
| model | string | 否 | null | 具体型号 |
| fault_type | string | 否 | null | 故障类型 |
| alarm_code | string | 否 | null | 告警代码 |
| alarm_info | string | 否 | null | 告警信息 |
| fault_description | string | 是 | 无 | 故障现象描述 |
| device_status | string | 否 | null | 当前设备状态 |
| include_references | boolean | 否 | true | 是否尝试返回知识库来源 |

## 请求示例

```json
{
  "manufacturer": "sungrow",
  "product_series": "SG",
  "device_type": "pv_inverter",
  "device_name": "1号方阵逆变器",
  "fault_type": "over_temperature",
  "alarm_code": "TEMP_HIGH",
  "alarm_info": "逆变器温度过高，出现降额运行",
  "fault_description": "阳光 SG 系列逆变器中午高温时频繁出现过温降额，发电功率下降。",
  "device_status": "warning",
  "include_references": true
}
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "possible_causes": [
      "逆变器散热风道堵塞或通风不良。",
      "风扇异常、转速不足或损坏。",
      "环境温度过高导致设备降额运行。",
      "设备长期高负载运行，内部温度超过阈值。"
    ],
    "inspection_steps": [
      "确认现场安全条件，避免在高温或带电风险下直接操作。",
      "查看逆变器温度、告警时间和降额曲线。",
      "检查进出风口是否被灰尘、杂物或遮挡物堵塞。",
      "检查风扇运行状态和异常噪声。",
      "清理散热通道后观察温度和功率是否恢复。"
    ],
    "safety_notes": [
      "检修前应遵守厂家手册和电站安全操作规程。",
      "高温状态下避免直接接触散热部件。",
      "涉及电气开盖检查时必须由具备资质人员执行。"
    ],
    "recommended_actions": [
      "清理逆变器风道和散热区域。",
      "检查或更换异常风扇。",
      "记录告警时间、环境温度和处理结果。",
      "如告警持续，应联系厂家技术支持。"
    ],
    "references": [
      {
        "document_id": "doc-002",
        "document_title": "阳光 SG 系列逆变器过温处理规程",
        "manufacturer": "sungrow",
        "product_series": "SG",
        "document_type": "sop",
        "section_title": "过温与风扇异常",
        "chunk_index": 1,
        "score": 0.79
      }
    ],
    "confidence": 0.74,
    "trace_id": "diag_20260527_001"
  }
}
```

## 数据库写入要求

每次调用必须写入 `diagnosis_records`：

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
```

## 验收标准

```text
1. 输入故障描述后返回 possible_causes
2. 返回 inspection_steps
3. 返回 safety_notes
4. 返回 recommended_actions
5. diagnosis_records 真实入库
6. trace_id 可追溯
7. 如 references 不为空，必须来自真实 knowledge_chunks
```

---

## 9. 检修任务接口

---

# 9.1 创建检修任务

## 接口

```http
POST /api/maintenance/tasks
```

## 说明

创建光伏逆变器检修任务，可由人工创建，也可由问答或诊断结果生成。

## 请求体字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| title | string | 是 | 无 | 任务标题 |
| manufacturer | string | 否 | null | huawei / sungrow |
| product_series | string | 否 | null | SUN2000 / FusionSolar / SG |
| device_type | string | 否 | pv_inverter | 光伏逆变器 |
| device_id | string/integer | 否 | null | 关联设备 |
| device_name | string | 否 | null | 设备名称 |
| model | string | 否 | null | 型号 |
| fault_type | string | 否 | null | 故障类型 |
| alarm_code | string | 否 | null | 告警代码 |
| fault_description | string | 否 | null | 故障描述 |
| priority | string | 否 | medium | low / medium / high / critical |
| assignee | string | 否 | null | 负责人 |
| due_date | string | 否 | null | 截止时间 |
| source_type | string | 否 | manual | manual / qa / diagnosis |
| source_trace_id | string | 否 | null | 来源 trace_id |
| suggested_steps | array | 否 | [] | 建议步骤 |

## 请求示例

```json
{
  "title": "处理华为 SUN2000 绝缘阻抗低告警",
  "manufacturer": "huawei",
  "product_series": "SUN2000",
  "device_type": "pv_inverter",
  "device_name": "2号方阵逆变器",
  "fault_type": "low_insulation_resistance",
  "alarm_code": "LOW_INSULATION",
  "fault_description": "设备出现绝缘阻抗低告警，需要现场检查直流侧组串和接地情况。",
  "priority": "high",
  "assignee": "maintenance_engineer",
  "source_type": "qa",
  "source_trace_id": "qa_20260527_001",
  "suggested_steps": [
    "查看告警代码和发生时间。",
    "检查直流侧组串和接地。",
    "检测绝缘阻抗。",
    "复检并记录结果。"
  ]
}
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "task-001",
    "title": "处理华为 SUN2000 绝缘阻抗低告警",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "device_type": "pv_inverter",
    "priority": "high",
    "task_status": "pending",
    "assignee": "maintenance_engineer",
    "source_type": "qa",
    "source_trace_id": "qa_20260527_001",
    "created_at": "2026-05-27T12:00:00+08:00"
  }
}
```

## 数据库写入要求

必须写入：

```text
maintenance_tasks
```

默认：

```text
task_status = pending
status = active
```

---

# 9.2 查询检修任务列表

## 接口

```http
GET /api/maintenance/tasks
```

## 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| manufacturer | string | 否 | null | 厂家 |
| product_series | string | 否 | null | 产品系列 |
| device_type | string | 否 | pv_inverter | 设备类型 |
| fault_type | string | 否 | null | 故障类型 |
| priority | string | 否 | null | 优先级 |
| task_status | string | 否 | null | 任务状态 |
| assignee | string | 否 | null | 负责人 |
| keyword | string | 否 | null | 标题或故障描述关键词 |

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "task-001",
        "title": "处理华为 SUN2000 绝缘阻抗低告警",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "fault_type": "low_insulation_resistance",
        "priority": "high",
        "task_status": "pending",
        "assignee": "maintenance_engineer",
        "created_at": "2026-05-27T12:00:00+08:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

---

# 9.3 查询任务详情

## 接口

```http
GET /api/maintenance/tasks/{task_id}
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "task-001",
    "title": "处理华为 SUN2000 绝缘阻抗低告警",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "device_type": "pv_inverter",
    "device_name": "2号方阵逆变器",
    "fault_type": "low_insulation_resistance",
    "alarm_code": "LOW_INSULATION",
    "fault_description": "设备出现绝缘阻抗低告警，需要现场检查直流侧组串和接地情况。",
    "priority": "high",
    "task_status": "pending",
    "assignee": "maintenance_engineer",
    "source_type": "qa",
    "source_trace_id": "qa_20260527_001",
    "suggested_steps": [
      "查看告警代码和发生时间。",
      "检查直流侧组串和接地。"
    ],
    "result_summary": null,
    "created_at": "2026-05-27T12:00:00+08:00",
    "updated_at": "2026-05-27T12:00:00+08:00"
  }
}
```

---

# 9.4 更新任务状态

## 接口

```http
POST /api/maintenance/tasks/{task_id}/start
POST /api/maintenance/tasks/{task_id}/complete
POST /api/maintenance/tasks/{task_id}/cancel
```

## 请求体字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| task_status | string | 是 | pending / in_progress / completed / cancelled |
| result_summary | string | 否 | 处理结果摘要 |
| completion_notes | string | 否 | 完成说明 |

## 请求示例

```json
{
  "task_status": "completed",
  "result_summary": "已完成直流侧组串绝缘检查，发现一处接插件受潮，处理后告警消除。",
  "completion_notes": "已复检并记录。"
}
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "task-001",
    "task_status": "completed",
    "result_summary": "已完成直流侧组串绝缘检查，发现一处接插件受潮，处理后告警消除。",
    "completed_at": "2026-05-27T15:30:00+08:00"
  }
}
```

## 状态流转规则

允许：

```text
pending -> in_progress
pending -> cancelled
in_progress -> completed
in_progress -> cancelled
```

不建议允许：

```text
completed -> pending
cancelled -> in_progress
```

非法流转返回 409。

---

## 10. 记录追溯接口

---

# 10.1 查询问答记录

## 接口

```http
GET /api/retrieval/records
```

## 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| manufacturer | string | 否 | null | 厂家 |
| product_series | string | 否 | null | 产品系列 |
| device_type | string | 否 | pv_inverter | 设备类型 |
| keyword | string | 否 | null | 问题关键词 |
| trace_id | string | 否 | null | 追溯编号 |

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "qa-001",
        "question": "华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "answer": "根据已入库资料...",
        "references": [
          {
            "document_id": "doc-001",
            "document_title": "华为 SUN2000 逆变器告警排查样例",
            "chunk_index": 0,
            "score": 0.82
          }
        ],
        "suggested_steps": [
          "确认安全条件。",
          "检查直流侧组串。"
        ],
        "confidence": 0.78,
        "trace_id": "qa_20260527_001",
        "created_at": "2026-05-27T12:00:00+08:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

## 验收标准

```text
1. 返回真实 qa_records
2. 能查询到最近一次 /api/retrieval/query 写入的记录
3. trace_id 与问答接口返回一致
4. references 被保存
5. suggested_steps 被保存
```

---

# 10.2 查询诊断记录

## 接口

```http
GET /api/diagnosis/records
```

## 查询参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| page | integer | 否 | 1 | 页码 |
| page_size | integer | 否 | 10 | 每页数量 |
| manufacturer | string | 否 | null | 厂家 |
| product_series | string | 否 | null | 产品系列 |
| fault_type | string | 否 | null | 故障类型 |
| alarm_code | string | 否 | null | 告警代码 |
| trace_id | string | 否 | null | 追溯编号 |

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "diag-001",
        "manufacturer": "sungrow",
        "product_series": "SG",
        "device_type": "pv_inverter",
        "fault_type": "over_temperature",
        "alarm_code": "TEMP_HIGH",
        "fault_description": "阳光 SG 系列逆变器中午高温时频繁过温降额。",
        "possible_causes": [
          "散热风道堵塞",
          "风扇异常",
          "环境温度过高"
        ],
        "inspection_steps": [
          "检查进出风口。",
          "检查风扇状态。"
        ],
        "safety_notes": [
          "检修前确认设备安全状态。"
        ],
        "recommended_actions": [
          "清理风道。",
          "更换异常风扇。"
        ],
        "confidence": 0.74,
        "trace_id": "diag_20260527_001",
        "created_at": "2026-05-27T12:00:00+08:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 10
  }
}
```

---

## 11. 设备接口

第一版可选实现设备管理接口。如果已有 `devices` 表，建议保留基础 CRUD。若开发资源紧张，可先只作为任务和诊断中的辅助字段，不强制实现完整设备台账页面。

---

# 11.1 创建设备

## 接口

```http
POST /api/devices
```

## 请求体示例

```json
{
  "name": "1号方阵华为逆变器",
  "code": "INV-HW-001",
  "manufacturer": "huawei",
  "product_series": "SUN2000",
  "model": "SUN2000-100KTL",
  "device_type": "pv_inverter",
  "site_name": "示范光伏电站",
  "location": "1号方阵",
  "status": "normal",
  "description": "示范设备"
}
```

## 成功响应示例

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "device-001",
    "name": "1号方阵华为逆变器",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "device_type": "pv_inverter",
    "status": "normal"
  }
}
```

---

# 11.2 查询设备列表

## 接口

```http
GET /api/devices
```

## 查询参数

```text
page
page_size
manufacturer
product_series
device_type
status
keyword
```

---

## 12. 前端调用规范

### 12.1 Axios 基础路径

前端统一使用：

```text
/api
```

不直接写死：

```text
http://127.0.0.1:8000
```

开发环境可通过 Vite proxy 转发。

---

### 12.2 前端不得假造成功数据

前端页面如接口失败，应显示错误提示。

禁止：

```text
接口失败后前端仍显示假数据
接口失败后提示“操作成功”
```

---

### 12.3 前端关键页面接口对应关系

| 页面 | 主要接口 |
|---|---|
| DashboardView | GET /api/system/status |
| KnowledgeBaseView | POST /api/knowledge/documents/upload, GET /api/knowledge/documents, GET /api/knowledge/documents/{id}/chunks |
| RetrievalChatView | POST /api/retrieval/query |
| FaultDiagnosisView | POST /api/diagnosis/analyze |
| MaintenanceTaskView | GET/POST/PUT /api/maintenance/tasks, POST /api/maintenance/tasks/{task_id}/assign, /start, /complete, /cancel |
| RecordCenterView | GET /api/record-center/overview, GET /api/record-center/search, GET /api/record-center/records/{record_type}/{record_id} |
| SystemStatusView | GET /api/health, GET /api/system/status |

---

## 13. OpenAPI 文档要求

FastAPI 自动生成的 OpenAPI 文档必须可访问：

```http
GET /docs
GET /openapi.json
```

验收标准：

```text
1. 所有核心接口出现在 /docs
2. 请求和响应 schema 清晰
3. 接口路径为 /api/...，不是公开版本化 API 前缀
4. 枚举字段在 schema 中有说明
```

---

## 14. 安全与输入限制

### 14.1 文件上传安全

```text
1. 限制扩展名：txt, md, pdf, docx
2. 限制文件大小：默认 50MB
3. 上传目录不得位于 frontend
4. 文件名必须清洗，防止路径穿越
5. 空文件返回 400
```

---

### 14.2 问答输入限制

```text
1. query/question 不能为空
2. query 建议最大长度 2000 字符
3. top_k 最大为 10
4. 不允许通过 query 注入数据库查询
```

---

### 14.3 枚举字段校验

涉及以下字段时必须校验：

```text
manufacturer
device_type
document_type
parse_status
fault_type
priority
task_status
```

非法枚举返回 400 或 422。

---

## 15. 真实闭环验收流程

以下流程是第一版 API 的核心验收流程。

### 15.1 数据库迁移

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

必须真实连接 PostgreSQL 成功。

---

### 15.2 上传华为样例文档

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_huawei_sun2000_alarm.txt" \
  -F "manufacturer=huawei" \
  -F "product_series=SUN2000" \
  -F "device_type=pv_inverter" \
  -F "document_type=alarm_code" \
  -F "source=local_sample"
```

验收：

```text
parse_status = parsed
chunk_count > 0
```

---

### 15.3 上传阳光样例文档

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_sungrow_sg_overtemperature.txt" \
  -F "manufacturer=sungrow" \
  -F "product_series=SG" \
  -F "device_type=pv_inverter" \
  -F "document_type=sop" \
  -F "source=local_sample"
```

---

### 15.4 查询 chunks

```bash
curl http://127.0.0.1:8000/api/knowledge/documents/{document_id}/chunks
```

验收：

```text
items 不为空
content 来自上传文件
manufacturer / product_series 正确
```

---

### 15.5 执行检修问答

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

验收：

```text
references 不为空
retrieved_chunks 不为空
trace_id 存在
answer 基于真实切片
qa_records 写入成功
```

---

### 15.6 查询问答记录

```bash
curl http://127.0.0.1:8000/api/retrieval/records
```

验收：

```text
能查到刚才的问题
trace_id 一致
references 已保存
```

---

### 15.7 执行故障诊断

```bash
curl -X POST http://127.0.0.1:8000/api/diagnosis/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "manufacturer": "sungrow",
    "product_series": "SG",
    "device_type": "pv_inverter",
    "fault_type": "over_temperature",
    "fault_description": "阳光 SG 系列逆变器中午高温时频繁出现过温降额。"
  }'
```

验收：

```text
possible_causes 不为空
inspection_steps 不为空
diagnosis_records 写入成功
```

---

### 15.8 创建检修任务

```bash
curl -X POST http://127.0.0.1:8000/api/maintenance/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "title": "处理阳光 SG 系列逆变器过温降额问题",
    "manufacturer": "sungrow",
    "product_series": "SG",
    "device_type": "pv_inverter",
    "fault_type": "over_temperature",
    "priority": "high",
    "assignee": "maintenance_engineer"
  }'
```

验收：

```text
maintenance_tasks 写入成功
task_status = pending
```

---

## 16. 禁止事项

后端 API 开发中禁止：

```text
1. 将对外路径改为公开版本化 API 前缀而不更新文档和前端
2. 使用内存模拟代替 PostgreSQL 写入
3. 伪造 references
4. 无检索结果时编造来源
5. API 层直接操作数据库
6. 把文件上传到 frontend 目录
7. 接口失败后仍返回 success
8. 把 Docker 作为 Energy-Maintenance 的正式部署路线
9. 将 Intelligent-Teaching 数据库作为正式依赖
10. 将业务范围扩展到泛新能源设备
```

---

## 17. 与其他文档的关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
03_database_schema_design.md
```

后续文档应与本文档保持一致：

```text
05_frontend_page_and_interaction_spec.md
06_knowledge_base_and_document_processing_spec.md
07_retrieval_qa_and_fault_diagnosis_spec.md
09_testing_acceptance_and_quality_spec.md
10_vibe_coding_task_plan.md
```

---

## 18. 下一步建议

本文档确认后，应继续编写：

```text
05_frontend_page_and_interaction_spec.md
```

下一份文档需要将本文档中的接口契约落实到前端页面：

```text
DashboardView
KnowledgeBaseView
RetrievalChatView
FaultDiagnosisView
MaintenanceTaskView
RecordCenterView
SystemStatusView
```

并明确每个页面的字段、按钮、筛选项、接口调用、加载态、空态、错误态和验收标准。
---

## Task 02A API 合同一致性补充

本补充用于约束后续接口设计，不在本轮新增后端接口实现。

### A. 公共路径

公共 API 前缀保持：

```text
/api
```

内部目录以 `app/api/routes` 为当前基线；无论内部目录如何组织，对外路径都保持 `/api/...`。

### B. P0 模块接口边界

后续接口应覆盖以下 P0 业务模块：

- auth：登录、当前用户、会话状态。
- users：用户列表、角色与状态管理。
- devices：设备台账、设备详情、设备维护历史。
- knowledge：文档上传、解析、切片、审核状态、知识贡献。
- media：故障图片和附件上传记录。
- retrieval：基于 PostgreSQL 知识切片和历史记录的检索问答。
- diagnosis：故障诊断、告警码查询、诊断记录。
- sop：SOP 模板和执行记录。
- tasks：检修任务创建、状态更新、任务详情。
- records：QA 记录、诊断记录、追溯中心。
- reviews：知识审核、模型输出纠错。

---

## Task 11 API 补充：记录中心、审核修正与系统统计

Task 11 在不新增 migration 的前提下，基于现有 PostgreSQL 表补充以下接口。所有接口继续使用 `/api` 前缀，并要求登录访问。

### 记录中心

```text
GET /api/record-center/overview
GET /api/record-center/search
GET /api/record-center/records/{record_type}/{record_id}
GET /api/record-center/devices/{device_id}/timeline
```

`record_type` 支持：

```text
all
qa
diagnosis
task
maintenance_record
sop_execution
knowledge_document
media
```

记录中心接口只读，用于统一查询 QA、诊断、检修任务、维修履历、SOP 执行、知识文档和上传媒体记录。

---

## Task 18K Final API Contract Calibration

This section is the delivery-facing API baseline after Task 18K. Use the current OpenAPI route set, not early-stage examples.

### Current public API route groups

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/logout

GET  /api/health
GET  /api/system/info
GET  /api/system/status
GET  /api/system/statistics

GET  /api/devices
POST /api/devices
GET  /api/devices/{device_id}
PUT  /api/devices/{device_id}
POST /api/devices/{device_id}/retire

POST /api/knowledge/documents/upload
GET  /api/knowledge/documents
GET  /api/knowledge/documents/{document_id}
GET  /api/knowledge/documents/{document_id}/chunks
DELETE /api/knowledge/documents/{document_id}

GET  /api/knowledge/contributions
POST /api/knowledge/contributions

POST /api/retrieval/query
GET  /api/retrieval/records
GET  /api/retrieval/records/{trace_id}

POST /api/diagnosis/analyze
GET  /api/diagnosis/records
GET  /api/diagnosis/records/{trace_id}

GET  /api/maintenance/tasks
POST /api/maintenance/tasks
GET  /api/maintenance/tasks/{task_id}
PUT  /api/maintenance/tasks/{task_id}
POST /api/maintenance/tasks/{task_id}/assign
POST /api/maintenance/tasks/{task_id}/start
POST /api/maintenance/tasks/{task_id}/complete
POST /api/maintenance/tasks/{task_id}/cancel

GET  /api/record-center/overview
GET  /api/record-center/search
GET  /api/record-center/records/{record_type}/{record_id}
GET  /api/record-center/devices/{device_id}/timeline

GET  /api/model-gateway/status
POST /api/model-gateway/test
POST /api/model-gateway/chat
GET  /api/media/ocr/status
GET  /api/kg/overview
POST /api/sop/generate
```

Legacy record route names, the legacy maintenance-diagnosis endpoint name, and public versioned API-prefix examples must not be used in final delivery materials.

### Capability boundary

- Real references must come from PostgreSQL knowledge documents, chunks, record-center data, media metadata, or KG evidence links.
- Cloud model, local llama.cpp, OCR, LoongArch/Kylin real-machine acceptance, pgvector/embedding retrieval, Neo4j, and image fault auto-recognition are not passed unless separately configured and verified.

### 知识审核

```text
GET  /api/review/knowledge
GET  /api/review/knowledge/{document_id}
POST /api/review/knowledge/{document_id}/approve
POST /api/review/knowledge/{document_id}/reject
POST /api/review/knowledge/{document_id}/archive
```

读取接口允许登录用户访问。审核写接口仅允许 `admin`、`expert` 调用。

### 输出修正

```text
POST /api/corrections
GET  /api/corrections
GET  /api/corrections/{correction_id}
POST /api/corrections/{correction_id}/resolve
```

`engineer` 可提交修正；`admin`、`expert` 可处理修正；`viewer` 仅可查看已公开处理的修正记录。

### 系统统计

```text
GET /api/system/statistics
```

统计数据来自真实 PostgreSQL 表，包含设备、知识库、QA、诊断、检修任务、SOP、维修履历、上传媒体和修正记录统计。
- model_gateway：模型服务配置、调用日志、可用性检查。
- system：健康检查、数据库状态、知识库统计。

### C. 统一响应与追溯字段

所有接口保持统一响应结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

写入型接口应返回或保存 `trace_id`。检索与诊断类接口的 `references` 必须来自真实数据库记录，不允许由前端或 API 层编造来源。

### D. P0 请求字段约定

设备、知识、问答、诊断、任务相关接口应优先包含：

- manufacturer。
- product_series。
- model。
- device_type。
- fault_type。

---

## Task 12 API 补充：Model Gateway

Task 12 新增模型网关接口，公共前缀继续使用 `/api`，不改动既有业务接口路径。

```text
GET  /api/model-gateway/status
POST /api/model-gateway/test
POST /api/model-gateway/chat
GET  /api/model-gateway/logs
GET  /api/model-gateway/logs/{log_id}
```

访问控制：

- `status`、`logs`、`logs/{log_id}`：登录用户可读。
- `test`、`chat`：仅 `admin`、`expert`、`engineer` 可调用。
- `viewer` 为只读角色，不允许发起模型测试或模型调用。

Provider：

```text
rule_based
local_llama_cpp
cloud_openai
```

响应继续使用统一结构：

```json
{
  "code": 200,
  "message": "success",
  "data": {}
}
```

约束：

- `rule_based` 是默认兜底，不代表真实大模型。
- `local_llama_cpp` 未启用或不可达时应返回结构化错误或规则兜底，不得导致系统崩溃。
- `cloud_openai` 只有在 `.env` 显式启用且配置 API key 后才允许真实调用。
- API key 不得出现在响应体、日志详情、前端页面或报告中。
- 调用日志写入已有 `model_call_logs` 表，本任务不新增数据库字段。
- alarm_code。
- source_trace_id。

第一版本新增前端选项和请求字段应使用 `pv_inverter` 表示光伏逆变器，历史 `inverter` 可作为兼容值处理。

---

## Task 13 API 补充：业务接口模型增强字段

Task 13 在既有业务接口上增加可选模型增强字段，不新增 API 路径，不修改数据库结构，不生成 Alembic migration。

适用接口：

```text
POST /api/retrieval/query
POST /api/diagnosis/analyze
POST /api/sop/generate
```

可选请求字段：

```json
{
  "enable_model_enhancement": false,
  "model_provider": "rule_based",
  "allow_model_fallback": true
}
```

响应补充字段：

```json
{
  "model_enhanced": false,
  "fallback_used": false,
  "model_provider": "rule_based",
  "model_name": "rule_or_gateway_model_name",
  "model_call_trace_id": null
}
```

---

## Task 14B API Contract Addendum: Cloud Model Status

`GET /api/model-gateway/status` may include `availability_status` for each provider:

```text
disabled
not_configured
not_checked
available
unavailable
```

For `cloud_openai`, `not_checked` means the provider is enabled and configured, but the status endpoint has not made a paid or token-consuming cloud request. Real availability is verified by `POST /api/model-gateway/test`, `POST /api/model-gateway/chat`, or business model-enhancement calls.

The response must never expose `CLOUD_LLM_API_KEY`. Logs may store `api_key_configured=true/false`, but not the key value.

约束：

- 不传新增字段时，接口保持原有 rule-based 行为。
- `enable_model_enhancement=false` 时不调用 Model Gateway。
- `enable_model_enhancement=true` 时，必须先完成原有检索、诊断或 SOP 规则流程，再调用 Model Gateway 进行表达增强。
- 模型增强失败时，业务接口必须回退原有规则结果，且 `fallback_used=true`。
- `references`、`retrieved_chunks`、`related_history` 和 SOP `references` 仍必须来自真实数据库记录，不允许由模型新增、删除或改写。
- 模型调用写入已有 `model_call_logs` 表；本任务不新增字段。
- `cloud_openai` 仅在 `.env` 显式启用并配置 API key 后才允许真实调用，API key 不得返回前端或写入日志响应。
---

## Task 18B API Addendum: Frontline Knowledge Contributions

Task 18B adds a role-gated contribution workflow without changing the `/api` prefix and without adding a migration.

Endpoints:

```text
GET  /api/knowledge/contributions
POST /api/knowledge/contributions
GET  /api/knowledge/contributions/{contribution_id}
PUT  /api/knowledge/contributions/{contribution_id}
POST /api/knowledge/contributions/{contribution_id}/submit
POST /api/knowledge/contributions/{contribution_id}/request-changes
POST /api/knowledge/contributions/{contribution_id}/approve
POST /api/knowledge/contributions/{contribution_id}/reject
POST /api/knowledge/contributions/{contribution_id}/convert-to-document
POST /api/knowledge/contributions/{contribution_id}/archive
```

State values:

```text
draft
submitted
changes_requested
approved
rejected
converted
archived
```

RBAC:

- `engineer`: create draft, edit own editable contribution, submit.
- `expert` / `admin`: request changes, approve, reject, convert to document, archive.
- `viewer`: read-only list/detail for approved or converted contributions.

Conversion must create a real `knowledge_documents` row and real `knowledge_chunks` rows. References returned by retrieval after conversion must come from those chunks, not from fabricated frontend data.

---

## Task 18C Knowledge Graph API Supplement

Task 18C adds PostgreSQL-backed knowledge graph APIs under `/api/kg`:

- `GET /api/kg/overview`
- `GET /api/kg/nodes`
- `POST /api/kg/nodes`
- `GET /api/kg/nodes/{node_id}`
- `PUT /api/kg/nodes/{node_id}`
- `POST /api/kg/nodes/{node_id}/archive`
- `POST /api/kg/nodes/{node_id}/merge`
- `GET /api/kg/edges`
- `POST /api/kg/edges`
- `GET /api/kg/edges/{edge_id}`
- `PUT /api/kg/edges/{edge_id}`
- `POST /api/kg/edges/{edge_id}/archive`
- `GET /api/kg/evidence`
- `POST /api/kg/evidence`
- `GET /api/kg/neighborhood/{node_id}`
- `GET /api/kg/path`
- `POST /api/kg/extract/from-document/{document_id}`
- `POST /api/kg/extract/from-contribution/{contribution_id}`
- `POST /api/kg/extract/from-record/{record_type}/{record_id}`
- `GET /api/kg/extraction-runs`
- `GET /api/kg/extraction-runs/{run_id}`
- `GET /api/kg/candidates`
- `GET /api/kg/candidates/{candidate_id}`
- `POST /api/kg/candidates/{candidate_id}/approve`
- `POST /api/kg/candidates/{candidate_id}/reject`

Graph extraction creates pending candidates. Expert/admin approval is required before candidates become formal graph nodes or edges.

---

## Task 18D Knowledge Graph Business API Addendum

Task 18D keeps the public API prefix as `/api` and adds business-facing graph read APIs. It does not add a migration and does not change existing API paths.

New read endpoints:

```text
GET /api/kg/graph
GET /api/kg/search
GET /api/kg/business-context
```

`GET /api/kg/graph` returns active graph nodes and edges for frontend visualization. It may filter by manufacturer, product series, fault type, node type, keyword, and depth.

`GET /api/kg/search` searches active graph nodes and edges. It returns evidence summaries only from real `kg_evidence_links`.

`GET /api/kg/business-context` groups active graph context for retrieval, diagnosis, and SOP flows. It may return:

```text
matched_nodes
related_faults
related_alarms
related_causes
inspection_items
recommended_actions
safety_risks
related_sop
tools
parts
evidence
graph_paths
kg_nodes
kg_edges
summary
```

Business request enhancement flag:

```json
{
  "enable_kg_enhancement": true
}
```

Supported by:

```text
POST /api/retrieval/query
POST /api/diagnosis/analyze
POST /api/sop/generate
```

Response additions:

- retrieval responses may include `kg_context`, `kg_nodes`, `kg_edges`, `kg_evidence`, and `kg_paths`.
- diagnosis responses may include `kg_context`, `kg_related_causes`, `kg_inspection_items`, `kg_recommended_actions`, `kg_safety_risks`, and `kg_evidence`.
- SOP responses may include `kg_context`, `kg_tools`, `kg_parts`, `kg_safety_risks`, `kg_steps`, and `kg_evidence`.
- record-center detail responses may include `knowledge_graph` summaries for traceability.

Rules:

- Only active graph nodes and active graph edges participate in business enhancement.
- References, evidence, graph paths, and related nodes must come from real PostgreSQL records.
- If no relevant graph context is found, graph fields should be empty or null; the backend must not fabricate graph facts.
- `enable_kg_enhancement=false` keeps the original non-graph business behavior.
- Neo4j, pgvector, embedding, OCR, and real model graph extraction are not required by this API contract.
## Task 22A Agent Runtime API Addendum

Task 22A adds the first Agent Runtime API foundation under the existing `/api` prefix. These APIs use the same unified response envelope as existing modules.

New endpoints:

```text
GET  /api/agents/definitions
GET  /api/agents/definitions/{agent_code}
GET  /api/agents/tools
GET  /api/agents/runs
POST /api/agents/runs
GET  /api/agents/runs/{run_id}
POST /api/agents/runs/{run_id}/cancel
GET  /api/agents/runs/{run_id}/steps
GET  /api/agents/runs/{run_id}/tool-calls
GET  /api/agents/runs/{run_id}/approvals
POST /api/agents/approvals/{approval_id}/approve
POST /api/agents/approvals/{approval_id}/reject
GET  /api/agents/runs/{run_id}/artifacts
GET  /api/agents/events
```

Boundary:

- `POST /api/agents/runs` only creates `rule_based_demo` / `dry_run` runs in Task 22A.
- `media_mimo_analysis` is a disabled, external-blocked tool placeholder.
- Real `mimo-2.5`, cloud model, local model, embedding, pgvector, and OCR execution are not claimed as completed by this API addendum.
# Task 22B Agent Business Tool API Note

Task 22B keeps the public API prefix as `/api` and enhances the existing agent runtime APIs without changing earlier business API paths.

Enhanced:

```text
POST /api/agents/runs
```

The payload may include `tools`, `tool_names`, `media_ids`, `input_media_ids`, `tool_inputs`, `context`, and `dry_run`.

Added:

```text
POST /api/agents/runs/{run_id}/execute-tool
```

This endpoint executes one registered business tool against an existing agent run. It is restricted to `admin`, `expert`, and `engineer`; `viewer` is blocked.

No Task 22B API calls use `/api/v1`, Docker, SQLite, embedding, pgvector, cloud model calls, or real OCR execution.

---

## Task 22C External API Provider Gateway

The following endpoints are available for reserved external API provider management and dry-run verification. They do not call real external APIs in Task 22C.

- `GET /api/external-apis/providers`
- `GET /api/external-apis/providers/{provider_code}`
- `GET /api/external-apis/routes`
- `GET /api/external-apis/status`
- `POST /api/external-apis/providers/{provider_code}/check`
- `POST /api/external-apis/dry-run`
- `GET /api/external-apis/logs`
- `GET /api/external-apis/logs/{trace_id}`
- `GET /api/external-apis/health-checks`

Response data must not include real API keys, Authorization headers, full image base64 data, or local file paths. `dry-run` returns `blocked` or `would_call` semantics and always sets `external_api_called=false` during Task 22C.

## Task 22D Multimodal Evidence Center

The multimodal evidence center provides media processing jobs, OCR result records, AI analysis records, evidence links, and media evidence summaries.

New endpoints:

- `GET /api/multimodal/media/{media_id}/jobs`
- `POST /api/multimodal/media/{media_id}/jobs`
- `GET /api/multimodal/jobs/{job_id}`
- `POST /api/multimodal/jobs/{job_id}/cancel`
- `GET /api/multimodal/media/{media_id}/ocr-results`
- `GET /api/multimodal/ocr-results/{result_id}`
- `GET /api/multimodal/media/{media_id}/analyses`
- `GET /api/multimodal/analyses/{analysis_id}`
- `POST /api/multimodal/analyses/{analysis_id}/review`
- `GET /api/multimodal/evidence-links`
- `POST /api/multimodal/evidence-links`
- `GET /api/multimodal/media/{media_id}/summary`

In Task 22D, job creation records provider blocked/dry-run status through the External API Provider Gateway. It does not perform real OCR, mimo-2.5, or cloud vision calls.
## Task 22E Addendum: External API Adapter Contract

The current public API keeps the `/api` prefix. Task 22E adds a local-only mock-run endpoint while preserving existing paths:

```text
POST /api/external-apis/dry-run
POST /api/external-apis/mock-run
POST /api/multimodal/media/{media_id}/jobs
```

`/api/external-apis/mock-run` is restricted to admin/expert users and returns `status=mocked`, `external_api_called=false`, and a normalized result with `mocked=true`.

`POST /api/multimodal/media/{media_id}/jobs` accepts `dry_run`, `mock_run`, `capability`, and `analysis_type`. Mock-run can persist local contract results to `media_ai_analyses` or `media_ocr_results`; these results are marked as mocked and not for production.

No real mimo-2.5, cloud vision, or OCR external API call is claimed in this stage.

## Task 22F Frontend API Usage Update

Task 22F adds a frontend route `/multimodal` and uses the existing `/api/multimodal`, `/api/external-apis`, `/api/media`, and `/api/agents` contracts.

No public API path was renamed. The page calls real backend APIs for provider status, dry-run, mock-run, media processing jobs, OCR results, AI analyses, evidence links, and Agent Run details.

The frontend must keep provider keys, trace fields, model names, and enum values unchanged when submitting requests. User-facing labels may be localized, but API payload values remain English keys.

Real external API calls remain blocked/not configured unless a later task supplies credentials and validates the provider.
## Task 22G Addendum: Multimodal Evidence Agent Timeline

Task 22G keeps the existing public API prefix `/api` and reuses `POST /api/agents/runs`.

When `agent_code=multimodal_evidence_agent`, the backend runs the dedicated multimodal evidence orchestration flow. The request may include `media_ids`, `tools`, `dry_run`, `mock_run`, and PV inverter context fields. `mock_run` is limited to expert/admin users.

Added read endpoint:

```text
GET /api/agents/runs/{run_id}/timeline
```

The response aggregates `run`, `steps`, `tool_calls`, `artifacts`, `approvals`, and `events`. It does not expose API keys, Authorization headers, base64 image payloads, or local file paths.

## Task 22H Addendum: Diagnosis / SOP / Task Agent Orchestration

Task 22H keeps the existing public API prefix `/api` and reuses the Agent Runtime API.

Dedicated orchestration is selected by `POST /api/agents/runs` with one of these `agent_code` values:

```text
fault_diagnosis_agent
sop_planner_agent
task_orchestration_agent
```

The request may include `device_id`, `media_ids`, `input_text`, `dry_run`, `mock_run`, `tools`, and PV inverter context fields such as `manufacturer`, `product_series`, `fault_type`, and `alarm_code`.

Read APIs remain the existing Agent Runtime APIs:

```text
GET /api/agents/runs/{run_id}
GET /api/agents/runs/{run_id}/timeline
GET /api/agents/runs/{run_id}/steps
GET /api/agents/runs/{run_id}/tool-calls
GET /api/agents/runs/{run_id}/artifacts
GET /api/agents/runs/{run_id}/approvals
POST /api/agents/approvals/{approval_id}/approve
POST /api/agents/approvals/{approval_id}/reject
```

Generated artifact types include:

- `diagnosis_summary`
- `sop_draft`
- `task_draft`
- `safety_checklist`
- `evidence_trace_summary`

Approval records are created for high-risk draft outputs:

- `approval_type=sop_draft_review`, `requested_action=review_sop_draft`
- `approval_type=task_draft_review`, `requested_action=review_task_draft`

Approving or rejecting these records only changes `agent_approvals`. It does not create formal SOP executions, formal SOP templates, formal maintenance tasks, or maintenance task status changes.

No real external API, OCR, pgvector, embedding, Neo4j, Docker, or SQLite capability is introduced by this addendum.

## Task 22J Addendum: Agent Artifact Conversion

Task 22J keeps the existing public API prefix `/api` and adds controlled conversion APIs for approved Agent draft artifacts.

New endpoints:

```text
GET  /api/agents/artifacts/{artifact_id}/conversion-status
POST /api/agents/artifacts/{artifact_id}/convert
GET  /api/agents/conversions
GET  /api/agents/conversions/{conversion_trace_id}
```

Request body for conversion:

```json
{
  "target_type": "knowledge_contribution | sop_template | maintenance_task | kg_candidate",
  "approval_id": "uuid",
  "override_warnings": false,
  "comment": "manual conversion note"
}
```

Supported artifact-to-target mapping:

- `knowledge_contribution_draft` -> `knowledge_contribution`
- `sop_draft` -> `sop_template`
- `task_draft` -> `maintenance_task`
- `kg_candidate_suggestion` -> `kg_candidate`

Approval does not automatically convert artifacts. `expert` or `admin` must explicitly call the conversion endpoint. `viewer` and `engineer` are blocked from conversion.

Conversion records are audited through `agent_event_logs` with `event_type=draft_converted_to_formal_object`. Duplicate conversion of the same artifact to the same target type is blocked.

Boundary:

- knowledge contribution conversion does not create `knowledge_documents` or `knowledge_chunks`;
- SOP conversion does not create `sop_execution_records`;
- task conversion does not start/complete a task and does not create `device_maintenance_records`;
- KG conversion creates pending `kg_candidates` only, not formal `kg_nodes` or `kg_edges`;
- no real external API, OCR, embedding, pgvector, Neo4j, Docker, SQLite, or delivery package generation is introduced.

## Task 22I Addendum: Knowledge Curator Agent

Task 22I keeps the existing public API prefix `/api` and reuses the Agent Runtime API.

Dedicated orchestration is selected by `POST /api/agents/runs` with:

```text
agent_code=knowledge_curator_agent
```

The request may include `device_id`, `media_ids`, `input_text`, `dry_run`, `tools`, PV inverter context fields, `engineer_notes`, `source_agent_run_ids`, and `source_artifact_ids`.

Read and approval APIs remain the existing Agent Runtime APIs:

```text
GET /api/agents/runs/{run_id}
GET /api/agents/runs/{run_id}/timeline
GET /api/agents/runs/{run_id}/steps
GET /api/agents/runs/{run_id}/tool-calls
GET /api/agents/runs/{run_id}/artifacts
GET /api/agents/runs/{run_id}/approvals
POST /api/agents/approvals/{approval_id}/approve
POST /api/agents/approvals/{approval_id}/reject
```

Generated artifact types include:

- `maintenance_case_summary`
- `knowledge_contribution_draft`
- `kg_candidate_suggestion`
- `safety_checklist`
- `evidence_trace_summary`

The orchestrator creates one pending approval record:

- `approval_type=knowledge_contribution_draft_review`
- `requested_action=review_knowledge_contribution_draft`

Approving or rejecting this record only changes `agent_approvals`. Task 22I does not create formal `knowledge_contributions`, `knowledge_documents`, approved chunks, or formal knowledge-graph nodes/edges. Explicit formal conversion is handled by Task 22J.

No real external API, OCR, pgvector, embedding, Neo4j, Docker, or SQLite capability is introduced by this addendum.
## Task 24B Addendum: DashVector Hybrid RAG API

Task 24B uses `/api/vector-search` as the vector-index API prefix. The route stores only DashVector index metadata in PostgreSQL and does not expose raw vectors or API keys. The active endpoints are:

- `GET /api/vector-search/status`
- `GET /api/vector-search/runs`
- `GET /api/vector-search/runs/{run_id}`
- `GET /api/vector-search/documents/{document_id}/status`
- `GET /api/vector-search/chunks/{chunk_id}/status`
- `POST /api/vector-search/documents/{document_id}/index`
- `POST /api/vector-search/chunks/{chunk_id}/index`
- `POST /api/vector-search/reindex-stale`
- `POST /api/vector-search/test-query`

This API does not use `/api/embeddings` as the public Task 24B route and does not introduce pgvector. Real DashVector and real embedding API calls remain opt-in only and require separate online acceptance.

## Task 24D Addendum: Security Status and Sanitized Responses

`GET /api/system/status` now includes a sanitized `security` object for deployment and acceptance checks. It may expose boolean/configuration-status fields such as `cors_configured`, `rate_limit_enabled`, `request_size_limit_enabled`, `secret_key_configured`, `admin_password_configured`, `dashvector_key_configured`, `embedding_key_configured`, `cloud_llm_key_configured`, `mimo_key_configured`, and `ocr_key_configured`.

The API contract forbids returning raw API keys, Authorization headers, tokens, passwords, local absolute paths, or base64 media payloads. External provider, model gateway, vector, OCR, MIMO, and agent log endpoints must expose only sanitized summaries and blocked/configured status.

Oversized JSON requests should return HTTP 413 with the unified response shape. Rate-limited requests should return HTTP 429. These protections do not change public route paths.

## Task 24E Addendum: Agent Artifact Conversion Audit APIs

Agent draft conversion now uses `agent_artifact_conversions` as the primary audit source. The API keeps existing conversion routes and adds history/detail lookup:

- `GET /api/agents/artifacts/{artifact_id}/conversion-status`
- `POST /api/agents/artifacts/{artifact_id}/convert`
- `GET /api/agents/conversions`
- `GET /api/agents/conversions/{conversion_trace_id}`
- `GET /api/agents/conversions/{conversion_id}/detail`
- `GET /api/agents/runs/{run_id}/conversions`
- `GET /api/agents/artifacts/{artifact_id}/conversions`

Approval and conversion remain separate. Only expert/admin users may convert approved artifacts. Duplicate or concurrent conversion of the same `source_artifact_id + target_type` must not create duplicate formal business objects.
