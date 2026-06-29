# Energy-Maintenance 数据库模型一致性审查

**文档版本：** v1.0  
**审查范围：** Task 02A 静态审查  
**审查日期：** 2026-06-01  

---

## 1. 审查范围

本次审查只进行文档、SQLAlchemy model、Alembic migration 的静态一致性检查，不连接 PostgreSQL，不执行 `alembic upgrade head`，不修改 `backend/app/models/`、`backend/app/schemas/` 或 `backend/alembic/versions/`。

审查对象：

- `backend/app/models/`
- `backend/alembic/versions/`
- `docs/03_database_schema_design.md`
- `docs/04_api_contract_design.md`
- `docs/11_detailed_requirements_analysis.md`
- `docs/12_functional_design_specification.md`

---

## 2. 当前发现的表

通过静态读取 SQLAlchemy metadata，当前模型已发现以下表：

| 表名 | 当前状态 |
| --- | --- |
| users | 已存在 |
| devices | 已存在 |
| knowledge_documents | 已存在 |
| knowledge_chunks | 已存在 |
| qa_records | 已存在 |
| diagnosis_records | 已存在 |
| maintenance_tasks | 已存在 |
| operation_logs | 已存在 |
| model_call_logs | 已存在 |

当前 Alembic 初始迁移中也包含上述核心表。由于本轮不执行数据库连接，尚未确认真实数据库实例中是否已经创建这些表。

---

## 3. 第一版本要求的表

第一版本 P0 和增强闭环建议覆盖以下表：

| 表名 | 类型 | 说明 |
| --- | --- | --- |
| users | 核心表 | 用户、角色、状态、密码哈希预留 |
| devices | 核心表 | 华为、阳光电源光伏逆变器设备台账 |
| uploaded_media | 新增表 | 故障图片、附件、上传文件媒体记录 |
| device_maintenance_records | 新增表 | 设备历史检修记录 |
| knowledge_documents | 核心表 | 知识文档元数据、解析状态、审核状态 |
| knowledge_chunks | 核心表 | 真实知识切片与来源追溯 |
| knowledge_contributions | 新增表 | 一线知识贡献 |
| knowledge_review_records | 新增表 | 知识审核记录 |
| model_output_corrections | 新增表 | 模型输出纠错记录 |
| qa_records | 核心表 | 检修问答记录 |
| diagnosis_records | 核心表 | 故障诊断记录 |
| maintenance_tasks | 核心表 | 检修任务 |
| sop_templates | 新增表 | SOP 模板 |
| sop_execution_records | 新增表 | SOP 执行记录 |
| operation_logs | 支撑表 | 操作日志 |
| model_call_logs | 支撑表 | 模型调用日志 |

---

## 4. 当前模型与目标模型映射

| 目标对象 | 当前表 | 对齐判断 |
| --- | --- | --- |
| 基础用户 | users | 部分对齐，需要补齐密码哈希等字段 |
| 设备台账 | devices | 基本对齐，需要确认第一版本枚举和值域 |
| 上传媒体 | uploaded_media | 缺失，需要在 Task 02B 中新增。 |
| 设备检修历史 | device_maintenance_records | 缺失，需要在 Task 02B 中新增。 |
| 知识文档 | knowledge_documents | 部分对齐，需要补齐审核相关字段 |
| 知识切片 | knowledge_chunks | 基本对齐，需要继续强化来源追溯能力 |
| 知识贡献 | knowledge_contributions | 缺失，需要在 Task 02B 中新增。 |
| 知识审核 | knowledge_review_records | 缺失，需要在 Task 02B 中新增。 |
| 模型输出纠错 | model_output_corrections | 缺失，需要在 Task 02B 中新增。 |
| 检修问答记录 | qa_records | 部分对齐，需要补齐模型提供方字段 |
| 故障诊断记录 | diagnosis_records | 部分对齐，需要补齐设备关联和历史关联字段 |
| 检修任务 | maintenance_tasks | 基本对齐，需要确认 device_id 外键约束 |
| SOP 模板 | sop_templates | 缺失，需要在 Task 02B 中新增。 |
| SOP 执行记录 | sop_execution_records | 缺失，需要在 Task 02B 中新增。 |
| 操作日志 | operation_logs | 已存在，可后续按审计要求增强 |
| 模型调用日志 | model_call_logs | 部分对齐，需要补齐 latency、success、prompt、response 语义字段 |

---

## 5. 缺失表清单

以下表当前未在 SQLAlchemy metadata 中发现：

| 表名 | 审查结论 |
| --- | --- |
| uploaded_media | 缺失，需要在 Task 02B 中新增。 |
| device_maintenance_records | 缺失，需要在 Task 02B 中新增。 |
| knowledge_contributions | 缺失，需要在 Task 02B 中新增。 |
| knowledge_review_records | 缺失，需要在 Task 02B 中新增。 |
| model_output_corrections | 缺失，需要在 Task 02B 中新增。 |
| sop_templates | 缺失，需要在 Task 02B 中新增。 |
| sop_execution_records | 缺失，需要在 Task 02B 中新增。 |

---

## 6. 需要增强的现有表

### 6.1 users

当前字段包含：

```text
username, display_name, role, status, is_active, id, created_at, updated_at
```

审查结论：

- role：已存在。
- status：已存在。
- password_hash / hashed_password：缺失，需要在 Task 02B 中新增。
- email、full_name 可作为 P0 或 P1 兼容字段补齐。

### 6.2 devices

当前字段包含：

```text
device_name, manufacturer, product_series, model, device_type, station_name, location, status, metadata_json, description, id, created_at, updated_at
```

审查结论：

- manufacturer：已存在。
- product_series：已存在。
- model：已存在。
- device_type：已存在。
- station_name：已存在。
- location：已存在。
- status：已存在。
- 建议在 Task 02B 中确认第一版本值域：manufacturer 仅 huawei、sungrow；device_type 优先 pv_inverter；product_series 为 SUN2000、FusionSolar、SG。

### 6.3 maintenance_tasks

当前字段包含：

```text
title, manufacturer, product_series, device_type, device_id, device_name, model, fault_type, alarm_code, fault_description, priority, task_status, assignee, due_date, source_type, source_trace_id, suggested_steps, result_summary, completion_notes, completed_at, id, created_at, updated_at
```

审查结论：

- device_id：字段已存在，但当前静态检查未发现 `ForeignKey("devices.id")`，建议 Task 02B 明确外键。
- source_type：已存在。
- source_trace_id：已存在。
- 建议补充 status transition 约束或在 service 层严格校验状态流转。

### 6.4 diagnosis_records

当前字段包含：

```text
manufacturer, product_series, device_type, device_name, model, fault_type, alarm_code, alarm_info, fault_description, device_status, possible_causes, inspection_steps, safety_notes, recommended_actions, references, confidence, trace_id, id, created_at, updated_at
```

审查结论：

- device_id：缺失，需要在 Task 02B 中新增。
- related_history：缺失，建议使用 JSONB 存储相关历史检修摘要。
- references：已存在。
- safety_notes：已存在。
- 建议 diagnosis_records 与 devices、uploaded_media、device_maintenance_records 建立可追溯关系。

### 6.5 qa_records

当前字段包含：

```text
question, normalized_query, manufacturer, product_series, device_type, document_type, answer, references, retrieved_chunks, suggested_steps, confidence, trace_id, id, created_at, updated_at
```

审查结论：

- references：已存在。
- retrieved_chunks：已存在。
- trace_id：已存在。
- model_provider：缺失，需要在 Task 02B 中新增。
- model_name 可与 model_call_logs 关联补充。

### 6.6 knowledge_documents

当前字段包含：

```text
title, manufacturer, product_series, model, device_type, document_type, source, file_name, file_path, file_size, file_ext, page_count, parse_status, parser_name, chunk_count, summary, error_message, metadata_json, parsed_at, status, id, created_at, updated_at
```

审查结论：

- review_status：缺失，需要在 Task 02B 中新增。
- submitted_by：缺失，需要在 Task 02B 中新增。
- reviewed_by：缺失，需要在 Task 02B 中新增。
- 建议补充 reviewed_at、review_comment。

### 6.7 knowledge_chunks

当前字段包含：

```text
document_id, manufacturer, product_series, device_type, document_type, chunk_index, content, section_title, char_count, page_number, embedding_status, metadata_json, status, id, created_at, updated_at
```

审查结论：

- document_id 外键已存在，支持从 chunk 追溯到 document。
- chunk_index、section_title、page_number、content 已存在，具备 references 基础支持。
- 建议在 Task 02B 中确认 manufacturer、product_series、device_type、document_type 与 document 同步写入策略。

### 6.8 model_call_logs

当前字段包含：

```text
trace_id, module, provider, model_name, prompt_tokens, completion_tokens, total_tokens, request_payload, response_payload, error_message, created_at, id
```

审查结论：

- provider：已存在。
- model_name：已存在。
- prompt：缺失，可由 request_payload 承载，但建议补充 prompt 或 prompt_text 便于审计。
- response：缺失，可由 response_payload 承载，但建议补充 response_text 便于追溯。
- latency：缺失，需要在 Task 02B 中新增 latency_ms。
- success：缺失，需要在 Task 02B 中新增。
- error_message：已存在。

---

## 7. 外键建议

Task 02B 建议补充或确认以下外键关系：

- `knowledge_chunks.document_id -> knowledge_documents.id`，当前已存在。
- `maintenance_tasks.device_id -> devices.id`。
- `diagnosis_records.device_id -> devices.id`。
- `device_maintenance_records.device_id -> devices.id`。
- `uploaded_media.device_id -> devices.id`，可为空。
- `uploaded_media.diagnosis_record_id -> diagnosis_records.id`，可为空。
- `knowledge_contributions.document_id -> knowledge_documents.id`，可为空。
- `knowledge_review_records.document_id -> knowledge_documents.id`。
- `sop_execution_records.sop_template_id -> sop_templates.id`。
- `sop_execution_records.task_id -> maintenance_tasks.id`，可为空。
- `model_output_corrections.qa_record_id -> qa_records.id`，可为空。
- `model_output_corrections.diagnosis_record_id -> diagnosis_records.id`，可为空。

---

## 8. JSONB 字段建议

以下字段建议使用 PostgreSQL JSONB：

- qa_records.references。
- qa_records.retrieved_chunks。
- qa_records.suggested_steps。
- diagnosis_records.possible_causes。
- diagnosis_records.inspection_steps。
- diagnosis_records.safety_notes。
- diagnosis_records.recommended_actions。
- diagnosis_records.references。
- diagnosis_records.related_history。
- knowledge_documents.metadata_json。
- knowledge_chunks.metadata_json。
- devices.metadata_json。
- maintenance_tasks.suggested_steps。
- uploaded_media.metadata_json。
- model_call_logs.request_payload。
- model_call_logs.response_payload。

---

## 9. Task 02B 数据库变更建议

Task 02B 建议按以下顺序执行：

1. 保持现有迁移链，新增一条 migration，不重置 migration 历史。
2. 新增缺失表：uploaded_media、device_maintenance_records、knowledge_contributions、knowledge_review_records、model_output_corrections、sop_templates、sop_execution_records。
3. 补齐 users.password_hash 或 hashed_password。
4. 补齐 knowledge_documents.review_status、submitted_by、reviewed_by、reviewed_at、review_comment。
5. 补齐 diagnosis_records.device_id、related_history。
6. 补齐 qa_records.model_provider、model_name。
7. 补齐 model_call_logs.prompt_text、response_text、latency_ms、success。
8. 确认 maintenance_tasks.device_id 外键和状态流转服务校验。
9. 同步更新 Pydantic schemas、repositories、services、API contracts 和 frontend types。

---

## 10. 是否继续旧迁移链

结论：继续旧迁移链。

原因：

- 当前已有初始迁移覆盖核心表。
- 重置迁移链会破坏已有开发环境的可升级路径。
- Task 02B 的工作属于新增表和补齐字段，适合通过新增 Alembic migration 完成。

---

## 11. 结论

当前数据库模型已经具备基础骨架：users、devices、knowledge_documents、knowledge_chunks、qa_records、diagnosis_records、maintenance_tasks、operation_logs、model_call_logs 均已存在。

但第一版本 P0 闭环仍缺少设备检修历史、上传媒体、知识贡献审核、模型输出纠错、SOP 模板和 SOP 执行记录等关键表；部分现有表也缺少审核、模型调用、设备关联和历史关联字段。

因此，本轮不能声明数据库模型已完全满足新版需求。建议在 Task 02B 中以新增迁移的方式补齐缺失表和字段，然后再执行真实 PostgreSQL migration、上传入库、检索问答、记录追溯闭环验收。
---

## 12. Task 02B 执行后静态复核

Task 02B 已根据本审查新增 SQLAlchemy models、Pydantic schemas 和 Alembic migration。静态 metadata 加载结果显示当前模型包含 16 张表：

```text
device_maintenance_records
devices
diagnosis_records
knowledge_chunks
knowledge_contributions
knowledge_documents
knowledge_review_records
maintenance_tasks
model_call_logs
model_output_corrections
operation_logs
qa_records
sop_execution_records
sop_templates
uploaded_media
users
```

### 12.1 缺失表处理结果

| 表名 | Task 02B 结果 |
| --- | --- |
| uploaded_media | 已新增 model、schema、migration |
| device_maintenance_records | 已新增 model、schema、migration |
| knowledge_contributions | 已新增 model、schema、migration |
| knowledge_review_records | 已新增 model、schema、migration |
| model_output_corrections | 已新增 model、schema、migration |
| sop_templates | 已新增 model、schema、migration |
| sop_execution_records | 已新增 model、schema、migration |

### 12.2 字段增强处理结果

- users 已补齐 password_hash、last_login_at。
- devices 已补齐 device_code、commissioning_date、last_fault_at、last_maintenance_at、fault_count、maintenance_count。
- knowledge_documents 已补齐 source_type、review_status、submitted_by、reviewed_by、reviewed_at、review_comment。
- knowledge_chunks 已补齐 content_hash。
- qa_records 已补齐 device_id、safety_notes、related_history、model_provider、model_name、created_by。
- diagnosis_records 已补齐 device_id、related_history、media_ids、model_provider、model_name、created_by。
- maintenance_tasks 已补齐 status、assignee_id、sop_template_id、sop_execution_id、root_cause、repair_action、replaced_parts、verification_result、is_recurrent、completed_by、created_by。
- model_call_logs 已补齐 call_type、prompt、response、latency_ms、success、created_by。

### 12.3 仍未完成的验收

本复核仍为静态检查。真实 PostgreSQL 迁移、真实外键约束创建、真实写入和查询闭环尚未执行，需要在 Task 03 中完成。
