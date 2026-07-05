# 03 数据库模式设计文档

**Document Name:** `03_database_schema_design.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Database:** PostgreSQL  
**ORM:** SQLAlchemy 2.x  
**Migration Tool:** Alembic  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版数据库模式设计，作为后续 vibe coding、数据库迁移、后端模型开发、接口开发和验收测试的统一依据。

本项目第一版已经明确收敛为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

因此，数据库设计必须围绕以下主线展开：

```text
华为 / 阳光电源
    ↓
光伏逆变器
    ↓
设备手册、告警代码、检修规程、故障案例、巡检规范
    ↓
知识切片
    ↓
检修问答
    ↓
故障诊断
    ↓
检修任务
    ↓
记录追溯
```

本文档不是泛化设备管理系统数据库设计，不面向所有新能源设备，不面向车辆维修，不面向教育平台，也不面向通用客服机器人。

---

## 2. 数据库设计原则

### 2.1 PostgreSQL 作为唯一正式关系型数据库

Energy-Maintenance 第一版正式数据库统一采用 PostgreSQL。

允许本地开发阶段临时连接任意可用 PostgreSQL 实例，但不得将 SQLite、MySQL 或其他数据库作为正式路线。

正式部署时数据库应运行在：

```text
LoongArch + Kylin + native PostgreSQL service
```

数据库连接必须通过环境变量读取：

```env
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@localhost:5432/energy_maintenance
```

代码中禁止写死数据库地址、用户名、密码和端口。

---

### 2.2 Alembic 是数据库结构变更的唯一依据

所有数据库表、字段、索引、约束的变更必须通过 Alembic migration 管理。

禁止直接手工修改生产数据库结构后不生成迁移脚本。

每次数据库变更必须满足：

```text
1. SQLAlchemy model 已更新
2. Pydantic schema 已同步
3. Repository 查询逻辑已同步
4. Alembic migration 已生成
5. README 或开发说明中补充迁移命令
6. 能通过 alembic upgrade head 创建或更新表结构
```

---

### 2.3 第一版以业务闭环为核心，不做过度数据建模

第一版数据库目标是支撑以下闭环：

```text
上传逆变器资料
    ↓
解析文本
    ↓
生成 knowledge_chunks
    ↓
检索真实 chunks
    ↓
生成检修问答
    ↓
保存 qa_records
    ↓
生成或关联检修任务
    ↓
保存完整追溯记录
```

因此，数据库优先保证以下能力：

```text
知识库可管理
切片可检索
来源可追溯
问答可保存
诊断可保存
任务可流转
状态可统计
```

暂不追求复杂多租户、复杂权限、复杂审批工作流、实时物联网数据建模。

---

## 3. 第一版核心实体

第一版核心表如下：

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

其中 MVP 必须打通的核心表为：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

`users`、`devices`、`operation_logs`、`model_call_logs` 可先具备基础结构，后续逐步增强。

---

## 4. 命名规范

### 4.1 表名规范

表名使用英文小写复数形式：

```text
knowledge_documents
knowledge_chunks
qa_records
diagnosis_records
maintenance_tasks
```

不得使用中文表名，不使用拼音，不使用无业务含义缩写。

---

### 4.2 字段命名规范

字段统一使用 snake_case：

```text
manufacturer
product_series
document_type
parse_status
created_at
updated_at
```

不得使用驼峰字段作为数据库列名。

---

### 4.3 枚举值命名规范

枚举值统一使用小写英文加下划线：

```text
huawei
sungrow
pv_inverter
alarm_code
fault_case
low_insulation_resistance
```

不得在数据库枚举值中直接使用中文。

---

## 5. 通用字段设计

除特殊关联表外，业务主表应尽量包含以下通用字段。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键。建议使用 UUID，也可使用 Integer 自增，需全项目统一 |
| status | String(32) | 是 | active | 业务状态 |
| created_at | DateTime(timezone=True) | 是 | now() | 创建时间 |
| updated_at | DateTime(timezone=True) | 是 | now() | 更新时间 |
| deleted_at | DateTime(timezone=True) | 否 | null | 软删除时间，可选 |
| created_by | UUID / Integer | 否 | null | 创建人，可后置 |
| updated_by | UUID / Integer | 否 | null | 更新人，可后置 |

第一版如尚未实现软删除，可先使用 `status` 表达业务状态，但应预留后续扩展空间。

---

## 6. 枚举值基线

### 6.1 manufacturer 厂家枚举

第一版仅支持两大主力厂家：

| 值 | 中文含义 | 说明 |
|---|---|---|
| huawei | 华为 | Huawei / SUN2000 / FusionSolar 体系 |
| sungrow | 阳光电源 | Sungrow / SG 系列 |

不建议第一版加入锦浪、固德威、古瑞瓦特等厂家，避免范围扩散。

---

### 6.2 product_series 产品系列枚举

| 厂家 | 值 | 中文含义 | 说明 |
|---|---|---|---|
| huawei | SUN2000 | 华为 SUN2000 系列 | 第一版主力系列 |
| huawei | FusionSolar | 华为 FusionSolar 体系 | 可作为监控与运维体系标识 |
| sungrow | SG | 阳光 SG 系列 | 第一版主力系列 |

说明：

`product_series` 不建议强制为数据库枚举类型，可用字符串字段约束在业务层校验，方便后续扩展具体型号，例如：

```text
SUN2000-50KTL
SUN2000-100KTL
SG110CX
SG320HX
```

---

### 6.3 device_type 设备类型枚举

第一版设备类型只聚焦光伏逆变器。

| 值 | 中文含义 | 说明 |
|---|---|---|
| pv_inverter | 光伏逆变器 | 第一版唯一核心设备类型 |
| other | 其他 | 仅用于兼容历史数据，不作为第一版页面主选项 |

不建议第一版继续暴露以下设备类型：

```text
battery
energy_storage
transformer
box_transformer
power_inspection_device
generic_renewable_equipment
```

这些可作为后续版本扩展，不进入第一版主线。

---

### 6.4 document_type 文档类型枚举

| 值 | 中文含义 | 说明 |
|---|---|---|
| manual | 设备手册 | 用户手册、安装手册、维护手册 |
| alarm_code | 告警代码 | 告警说明、错误码、事件码处理建议 |
| sop | 检修规程 | 标准作业规程、检修步骤 |
| fault_case | 故障案例 | 历史故障案例、模拟故障工单 |
| inspection_standard | 巡检规范 | 日常巡检项、周期性检查标准 |
| maintenance_record | 检修记录 | 维修记录、处理记录、复检记录 |

---

### 6.5 parse_status 文档解析状态

| 值 | 中文含义 | 说明 |
|---|---|---|
| pending | 待解析 | 文档元数据已创建，尚未解析 |
| processing | 解析中 | 正在提取文本和切片 |
| parsed | 已解析 | 文档解析成功，已生成知识切片 |
| failed | 解析失败 | 文档解析失败，应保存 error_message |

---

### 6.6 embedding_status 向量化状态

第一版不做真实 embedding，但字段应预留。

| 值 | 中文含义 | 说明 |
|---|---|---|
| pending | 待向量化 | 默认状态 |
| embedded | 已向量化 | 后续 pgvector 阶段使用 |
| failed | 向量化失败 | 后续 embedding 失败记录 |

---

### 6.7 task_status 检修任务状态

| 值 | 中文含义 | 说明 |
|---|---|---|
| pending | 待处理 | 新建任务 |
| in_progress | 处理中 | 检修人员正在处理 |
| completed | 已完成 | 检修完成并记录结果 |
| cancelled | 已取消 | 任务取消 |

---

### 6.8 priority 任务优先级

| 值 | 中文含义 | 说明 |
|---|---|---|
| low | 低 | 常规检查 |
| medium | 中 | 一般故障 |
| high | 高 | 影响发电或运行 |
| critical | 严重 | 可能存在安全风险或大范围停机 |

---

### 6.9 fault_type 典型故障类型

第一版重点围绕光伏逆变器典型故障。

| 值 | 中文含义 | 说明 |
|---|---|---|
| low_insulation_resistance | 绝缘阻抗低 | 直流侧、电缆、组件、接地相关排查 |
| dc_abnormal | 直流侧异常 | 直流输入、组串、接线、熔断器异常 |
| ac_overvoltage | 交流过压 | 电网侧电压异常 |
| ac_undervoltage | 交流欠压 | 电网侧欠压或并网条件异常 |
| grid_connection_fault | 并网异常 | 并网失败、频率/电压不满足条件 |
| over_temperature | 逆变器过温 | 散热、风扇、环境温度、降额运行 |
| fan_fault | 风扇异常 | 风扇堵转、损坏、散热不足 |
| communication_interruption | 通信中断 | 采集器、网络、FusionSolar/监控平台异常 |
| device_offline | 设备离线 | 设备离线、通信离线或停机 |
| mppt_abnormal | MPPT 异常 | 组串不均、MPPT 跟踪异常 |
| low_power_generation | 功率偏低 | 隐性损失、组串异常、遮挡、降额 |
| alarm_code_query | 告警代码查询 | 用户输入告警码并要求解释 |

---

## 7. 表设计详情

---

# 7.1 users 用户表

## 表名

```text
users
```

## 设计目的

用于预留系统用户、角色和后续权限控制。第一版可不实现完整登录鉴权，但用户表应具备基础结构。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| username | String(64) | 是 | 无 | 用户名，唯一 |
| full_name | String(128) | 否 | null | 姓名 |
| email | String(128) | 否 | null | 邮箱 |
| role | String(32) | 是 | operator | 角色 |
| hashed_password | String(255) | 否 | null | 密码哈希，第一版可预留 |
| is_active | Boolean | 是 | true | 是否启用 |
| status | String(32) | 是 | active | 状态 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |

## role 建议枚举

| 值 | 中文含义 |
|---|---|
| admin | 管理员 |
| engineer | 检修工程师 |
| operator | 运维人员 |
| viewer | 只读查看者 |

## 索引建议

```text
UNIQUE(username)
INDEX(role)
INDEX(status)
```

## 第一版要求

第一版不强制实现 JWT 登录，但数据库和代码结构应允许后续加入。

---

# 7.2 devices 设备表

## 表名

```text
devices
```

## 设计目的

用于管理逆变器设备基础信息。第一版可先用于检修任务和故障诊断中的设备引用，也可仅作为预留。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| name | String(128) | 是 | 无 | 设备名称 |
| code | String(128) | 否 | null | 设备编号或资产编号 |
| manufacturer | String(32) | 是 | huawei / sungrow | 厂家 |
| product_series | String(64) | 否 | null | 产品系列，如 SUN2000、FusionSolar、SG |
| model | String(128) | 否 | null | 设备型号 |
| device_type | String(32) | 是 | pv_inverter | 设备类型 |
| site_name | String(128) | 否 | null | 场站名称 |
| location | String(255) | 否 | null | 安装位置 |
| status | String(32) | 是 | normal | 设备状态 |
| description | Text | 否 | null | 备注 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |

## status 建议枚举

| 值 | 中文含义 |
|---|---|
| normal | 正常 |
| warning | 告警 |
| fault | 故障 |
| offline | 离线 |
| retired | 退役 |

## 索引建议

```text
INDEX(manufacturer)
INDEX(product_series)
INDEX(device_type)
INDEX(status)
INDEX(code)
```

## 第一版要求

设备表不一定是最核心，但 `manufacturer`、`product_series`、`device_type` 的设计必须与知识库、问答、诊断保持一致。

---

# 7.3 knowledge_documents 知识库文档表

## 表名

```text
knowledge_documents
```

## 设计目的

用于保存华为和阳光电源光伏逆变器相关知识资料的文档级元数据。

文档来源包括：

```text
设备手册
告警代码说明
检修规程
故障案例
巡检规范
检修记录
```

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| title | String(255) | 是 | 无 | 文档标题 |
| manufacturer | String(32) | 是 | 无 | 厂家：huawei / sungrow |
| product_series | String(64) | 否 | null | 产品系列：SUN2000 / FusionSolar / SG |
| model | String(128) | 否 | null | 具体型号，可选 |
| device_type | String(32) | 是 | pv_inverter | 设备类型 |
| document_type | String(64) | 是 | manual | 文档类型 |
| source | String(255) | 否 | null | 来源，如 official_manual、local_sample、user_upload |
| file_name | String(255) | 否 | null | 原始文件名 |
| file_path | String(512) | 否 | null | 文件保存路径 |
| file_size | Integer / BigInteger | 否 | null | 文件大小，单位 byte |
| file_ext | String(16) | 否 | null | 文件扩展名 |
| page_count | Integer | 否 | null | PDF/DOCX 页数或近似页数 |
| parse_status | String(32) | 是 | pending | 解析状态 |
| parser_name | String(64) | 否 | null | 解析器名称，如 pypdf、python-docx |
| chunk_count | Integer | 是 | 0 | 知识切片数量 |
| summary | Text | 否 | null | 文档摘要 |
| error_message | Text | 否 | null | 解析失败原因 |
| metadata_json | JSONB | 否 | null | 扩展元数据 |
| parsed_at | DateTime | 否 | null | 解析完成时间 |
| status | String(32) | 是 | active | 文档状态 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |

## 关键业务约束

1. `manufacturer` 第一版必须为 `huawei` 或 `sungrow`。
2. `device_type` 第一版默认 `pv_inverter`。
3. 只有 `parse_status = parsed` 且 `status = active` 的文档可以参与检索。
4. `chunk_count` 必须与 `knowledge_chunks` 实际数量保持一致。
5. 解析失败必须写入 `error_message`。

## metadata_json 建议结构

```json
{
  "upload_ip": "127.0.0.1",
  "parser_warnings": [],
  "original_title": "SUN2000 User Manual",
  "language": "zh-CN",
  "document_version": "v1.0"
}
```

## 索引建议

```text
INDEX(manufacturer)
INDEX(product_series)
INDEX(device_type)
INDEX(document_type)
INDEX(parse_status)
INDEX(status)
INDEX(created_at)
INDEX(title)
```

如后续使用 PostgreSQL 全文检索，可增加 GIN 索引。

## 第一版验收要求

上传文档后必须满足：

```text
knowledge_documents 新增记录
parse_status = parsed
chunk_count > 0
manufacturer / product_series / device_type / document_type 正确保存
```

---

# 7.4 knowledge_chunks 知识切片表

## 表名

```text
knowledge_chunks
```

## 设计目的

用于保存从知识库文档中解析、清洗、切片后的文本片段，是检索问答和故障诊断的主要知识来源。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| document_id | UUID / Integer | 是 | 无 | 外键，关联 knowledge_documents.id |
| manufacturer | String(32) | 是 | 无 | 冗余厂家字段，便于检索过滤 |
| product_series | String(64) | 否 | null | 冗余产品系列字段 |
| device_type | String(32) | 是 | pv_inverter | 冗余设备类型字段 |
| document_type | String(64) | 是 | 无 | 冗余文档类型字段 |
| chunk_index | Integer | 是 | 无 | 切片序号 |
| content | Text | 是 | 无 | 切片正文 |
| section_title | String(255) | 否 | null | 章节标题 |
| keywords | Text / JSONB | 否 | null | 关键词 |
| char_count | Integer | 是 | 0 | 字符数 |
| page_number | Integer | 否 | null | 来源页码 |
| embedding_status | String(32) | 是 | pending | 向量化状态 |
| metadata_json | JSONB | 否 | null | 扩展元数据 |
| status | String(32) | 是 | active | 状态 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |

## 是否需要冗余 manufacturer / product_series

建议在 `knowledge_chunks` 中冗余以下字段：

```text
manufacturer
product_series
device_type
document_type
```

原因：

```text
1. 提升检索过滤性能
2. 降低复杂 join 频率
3. 便于后续向量检索和混合检索
4. 便于构建 references
```

但必须保证创建 chunk 时从 document 中同步字段。

## metadata_json 建议结构

```json
{
  "source_file": "SUN2000_manual.pdf",
  "parser": "pypdf",
  "splitter": "paragraph_overlap",
  "chunk_size": 1000,
  "overlap": 150
}
```

## 索引建议

```text
INDEX(document_id)
INDEX(manufacturer)
INDEX(product_series)
INDEX(device_type)
INDEX(document_type)
INDEX(embedding_status)
INDEX(status)
INDEX(chunk_index)
```

如使用 PostgreSQL 全文检索，可增加：

```sql
CREATE INDEX idx_knowledge_chunks_content_tsv
ON knowledge_chunks
USING GIN (to_tsvector('simple', content));
```

第一版可先不创建全文索引，使用 SQLAlchemy 规则检索。

## 外键关系

```text
knowledge_chunks.document_id -> knowledge_documents.id
```

删除策略建议：

```text
文档软删除时，chunks 同步 status = inactive
文档硬删除时，可级联删除 chunks
```

## 第一版验收要求

上传并解析文档后必须满足：

```text
knowledge_chunks 至少生成 1 条记录
content 不为空
document_id 正确关联
manufacturer / device_type / document_type 与 document 一致
```

---

# 7.5 qa_records 问答记录表

## 表名

```text
qa_records
```

## 设计目的

用于保存用户每次检修知识问答的请求、回答、来源依据和追溯编号。

该表是体现系统“可追溯问答”的关键表。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| question | Text | 是 | 无 | 用户问题 |
| normalized_query | Text | 否 | null | 标准化后的检索问题 |
| manufacturer | String(32) | 否 | null | 厂家过滤 |
| product_series | String(64) | 否 | null | 产品系列过滤 |
| device_type | String(32) | 否 | pv_inverter | 设备类型 |
| document_type | String(64) | 否 | null | 文档类型过滤 |
| answer | Text | 是 | 无 | 系统回答 |
| references | JSONB | 否 | [] | 来源依据 |
| retrieved_chunks | JSONB | 否 | [] | 检索到的切片摘要 |
| suggested_steps | JSONB | 否 | [] | 建议检修步骤 |
| confidence | Float | 否 | null | 可信度，0-1 |
| trace_id | String(64) | 是 | 无 | 问答追溯编号 |
| user_id | UUID / Integer | 否 | null | 用户 ID |
| status | String(32) | 是 | active | 状态 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |

## references 结构

```json
[
  {
    "document_id": "uuid-or-int",
    "document_title": "SUN2000 用户手册",
    "manufacturer": "huawei",
    "product_series": "SUN2000",
    "document_type": "manual",
    "device_type": "pv_inverter",
    "section_title": "告警处理",
    "chunk_index": 3,
    "page_number": 12,
    "source": "official_manual",
    "score": 0.78
  }
]
```

## retrieved_chunks 结构

```json
[
  {
    "chunk_id": "uuid-or-int",
    "document_id": "uuid-or-int",
    "document_title": "SG 系列逆变器维护手册",
    "section_title": "过温处理",
    "content_preview": "当逆变器出现过温告警时，应检查散热风道...",
    "score": 0.81
  }
]
```

## suggested_steps 结构

```json
[
  "确认逆变器已按照安全规程停机或降载处理。",
  "查看监控平台告警代码和发生时间。",
  "检查直流侧组串、电缆、接地和绝缘情况。",
  "结合手册建议执行现场排查。",
  "处理后复检并记录结果。"
]
```

## 业务约束

1. 每次调用 `/api/retrieval/query` 必须写入 `qa_records`。
2. `trace_id` 必须唯一。
3. `references` 不允许编造，必须来自真实 `knowledge_chunks`。
4. 无检索结果时 `references = []`，不能伪造来源。
5. `confidence` 不能返回 1.0。

## 索引建议

```text
UNIQUE(trace_id)
INDEX(manufacturer)
INDEX(product_series)
INDEX(device_type)
INDEX(document_type)
INDEX(created_at)
```

---

# 7.6 diagnosis_records 故障诊断记录表

## 表名

```text
diagnosis_records
```

## 设计目的

用于保存故障辅助诊断的输入、诊断结果、排查步骤、安全提示和追溯信息。

第一版诊断逻辑可以是规则型，但诊断记录必须持久化。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| manufacturer | String(32) | 否 | null | 厂家 |
| product_series | String(64) | 否 | null | 产品系列 |
| device_type | String(32) | 是 | pv_inverter | 设备类型 |
| device_name | String(128) | 否 | null | 设备名称 |
| model | String(128) | 否 | null | 具体型号 |
| fault_type | String(64) | 否 | null | 故障类型 |
| alarm_code | String(64) | 否 | null | 告警代码 |
| alarm_info | Text | 否 | null | 告警信息 |
| fault_description | Text | 是 | 无 | 故障描述 |
| device_status | String(64) | 否 | null | 设备运行状态 |
| possible_causes | JSONB | 否 | [] | 可能原因 |
| inspection_steps | JSONB | 否 | [] | 排查步骤 |
| safety_notes | JSONB | 否 | [] | 安全注意事项 |
| recommended_actions | JSONB | 否 | [] | 推荐处理措施 |
| references | JSONB | 否 | [] | 来源依据，可后续接知识库 |
| confidence | Float | 否 | null | 可信度 |
| trace_id | String(64) | 是 | 无 | 诊断追溯编号 |
| user_id | UUID / Integer | 否 | null | 用户 ID |
| status | String(32) | 是 | active | 状态 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |

## 业务约束

1. 每次 `/api/diagnosis/analyze` 调用必须保存诊断记录。
2. 第一版可基于规则生成结果。
3. 后续应逐步结合 `knowledge_chunks` 检索来源。
4. `trace_id` 必须唯一。
5. 安全注意事项必须单独字段保存。

## 索引建议

```text
UNIQUE(trace_id)
INDEX(manufacturer)
INDEX(product_series)
INDEX(device_type)
INDEX(fault_type)
INDEX(alarm_code)
INDEX(created_at)
```

---

# 7.7 maintenance_tasks 检修任务表

## 表名

```text
maintenance_tasks
```

## 设计目的

用于管理由人工创建或由问答/诊断结果衍生的检修任务，实现从“知识问答”到“作业辅助”的闭环。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| title | String(255) | 是 | 无 | 任务标题 |
| manufacturer | String(32) | 否 | null | 厂家 |
| product_series | String(64) | 否 | null | 产品系列 |
| device_type | String(32) | 是 | pv_inverter | 设备类型 |
| device_id | UUID / Integer | 否 | null | 关联设备 ID |
| device_name | String(128) | 否 | null | 设备名称快照 |
| model | String(128) | 否 | null | 设备型号 |
| fault_type | String(64) | 否 | null | 故障类型 |
| alarm_code | String(64) | 否 | null | 告警代码 |
| fault_description | Text | 否 | null | 故障描述 |
| priority | String(32) | 是 | medium | 优先级 |
| task_status | String(32) | 是 | pending | 任务状态 |
| assignee | String(128) | 否 | null | 负责人 |
| due_date | DateTime | 否 | null | 截止时间 |
| source_type | String(32) | 否 | manual | 来源类型：manual / qa / diagnosis |
| source_trace_id | String(64) | 否 | null | 关联问答或诊断 trace_id |
| suggested_steps | JSONB | 否 | [] | 建议步骤 |
| result_summary | Text | 否 | null | 处理结果摘要 |
| completion_notes | Text | 否 | null | 完成说明 |
| status | String(32) | 是 | active | 业务状态 |
| created_at | DateTime | 是 | now() | 创建时间 |
| updated_at | DateTime | 是 | now() | 更新时间 |
| completed_at | DateTime | 否 | null | 完成时间 |

## source_type 枚举

| 值 | 中文含义 |
|---|---|
| manual | 人工创建 |
| qa | 由检修问答生成 |
| diagnosis | 由故障诊断生成 |

## 业务约束

1. 新建任务默认 `task_status = pending`。
2. 任务状态流转应遵循：

```text
pending -> in_progress -> completed
pending -> cancelled
in_progress -> cancelled
```

3. 完成任务时应填写 `result_summary` 或 `completion_notes`。
4. 从问答或诊断生成任务时，应保存 `source_trace_id`。

## 索引建议

```text
INDEX(manufacturer)
INDEX(product_series)
INDEX(device_type)
INDEX(fault_type)
INDEX(priority)
INDEX(task_status)
INDEX(assignee)
INDEX(created_at)
```

---

# 7.8 operation_logs 操作日志表

## 表名

```text
operation_logs
```

## 设计目的

用于记录用户关键操作，第一版可后置，但建议预留表结构。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| user_id | UUID / Integer | 否 | null | 用户 ID |
| action | String(128) | 是 | 无 | 操作动作 |
| module | String(64) | 是 | 无 | 模块名称 |
| target_type | String(64) | 否 | null | 目标类型 |
| target_id | String(64) | 否 | null | 目标 ID |
| detail | JSONB | 否 | null | 操作详情 |
| ip_address | String(64) | 否 | null | IP 地址 |
| user_agent | Text | 否 | null | 浏览器/客户端信息 |
| created_at | DateTime | 是 | now() | 创建时间 |

## 常见 action

```text
upload_document
delete_document
query_retrieval
diagnose_fault
create_task
update_task_status
```

---

# 7.9 model_call_logs 模型调用日志表

## 表名

```text
model_call_logs
```

## 设计目的

用于后续接入 embedding、大模型、OCR、多模态模型时记录模型调用。第一版可后置。

## 字段设计

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| id | UUID / Integer | 是 | 自动生成 | 主键 |
| trace_id | String(64) | 否 | null | 关联业务追溯编号 |
| model_type | String(64) | 是 | 无 | llm / embedding / ocr / multimodal |
| provider | String(64) | 否 | null | 模型提供方 |
| model_name | String(128) | 否 | null | 模型名称 |
| request_payload | JSONB | 否 | null | 请求摘要，不保存敏感完整内容 |
| response_summary | JSONB | 否 | null | 响应摘要 |
| status | String(32) | 是 | success | 调用状态 |
| error_message | Text | 否 | null | 错误信息 |
| latency_ms | Integer | 否 | null | 耗时 |
| created_at | DateTime | 是 | now() | 创建时间 |

---

## 8. 表关系设计

核心关系如下：

```text
knowledge_documents 1 --- N knowledge_chunks

qa_records N --- N knowledge_chunks
  第一版不单独建中间表，可通过 references JSONB 保存引用关系

diagnosis_records 可引用 knowledge_chunks
  第一版可通过 references JSONB 保存

maintenance_tasks 可由 qa_records 或 diagnosis_records 派生
  第一版通过 source_trace_id 关联
```

第一版不强制建立复杂多对多关系表，原因是：

```text
1. references JSONB 能满足来源追溯展示
2. 避免过早复杂化
3. 后续如需统计引用频率，可再设计 qa_record_references 表
```

---

## 9. 是否需要独立 reference 表

第一版不建议新建复杂引用表。

如果后续需要更严格的统计和追溯，可新增：

```text
qa_record_references
diagnosis_record_references
```

建议结构：

```text
id
record_id
record_type
chunk_id
document_id
score
rank
created_at
```

但第一版先使用 JSONB 存储 references，确保开发效率和接口灵活性。

---

## 10. JSONB 使用规范

PostgreSQL JSONB 可用于保存结构化但变化较快的数据，例如：

```text
references
retrieved_chunks
suggested_steps
possible_causes
inspection_steps
safety_notes
recommended_actions
metadata_json
```

但以下数据不应只放在 JSONB 中：

```text
manufacturer
product_series
device_type
document_type
parse_status
task_status
fault_type
trace_id
created_at
```

这些字段需要独立列，便于过滤、索引和统计。

---

## 11. 索引设计总览

### 11.1 knowledge_documents

```text
manufacturer
product_series
device_type
document_type
parse_status
status
created_at
```

### 11.2 knowledge_chunks

```text
document_id
manufacturer
product_series
device_type
document_type
embedding_status
status
chunk_index
```

### 11.3 qa_records

```text
trace_id unique
manufacturer
product_series
device_type
document_type
created_at
```

### 11.4 diagnosis_records

```text
trace_id unique
manufacturer
product_series
device_type
fault_type
alarm_code
created_at
```

### 11.5 maintenance_tasks

```text
manufacturer
product_series
device_type
fault_type
priority
task_status
assignee
created_at
```

---

## 12. PostgreSQL 扩展规划

第一版不强制开启 pgvector。

Task 24B 采用 DashVector 作为后续向量召回路线，不在 PostgreSQL 中启用 pgvector 扩展，也不在本地表中保存 raw vector。

若后续进入真实 DashVector 在线验收阶段，可继续复用 `knowledge_chunk_vector_indexes` 与 `vector_index_runs` 保存索引元数据和运行记录，并由外部向量库保存向量内容。

旧的 PostgreSQL pgvector 扩展示例已废弃，不作为当前迁移或部署指引。

当前不在 `knowledge_chunks` 中新增本地向量字段。DashVector 路线使用独立元数据表记录外部索引状态：

```text
knowledge_chunk_vector_indexes
vector_index_runs
```

但该能力不属于第一版 MVP，不能阻塞当前基于关键词的真实闭环。

---

## 13. SQLAlchemy 模型开发要求

### 13.1 模型分文件建议

```text
backend/app/models/
├── user.py
├── device.py
├── knowledge.py
├── record.py
├── maintenance.py
├── operation_log.py
└── model_call_log.py
```

### 13.2 Base metadata 必须被 Alembic 正确导入

`backend/alembic/env.py` 必须能导入所有模型，使 migration 能识别全部表。

禁止出现：

```text
模型文件存在，但 Alembic target_metadata 未导入，导致 migration 漏表
```

### 13.3 不要在 API 层直接操作模型

API 层只负责请求参数和响应。

正确结构：

```text
api -> service -> repository -> model
```

---

## 14. Pydantic Schema 同步要求

每张核心表应至少有：

```text
Create schema
Read schema
Update schema
List query schema
Page response schema
```

例如：

```text
KnowledgeDocumentCreate
KnowledgeDocumentRead
KnowledgeDocumentUpdate
KnowledgeDocumentListQuery
KnowledgeChunkRead
QARecordRead
DiagnosisRecordRead
MaintenanceTaskCreate
MaintenanceTaskRead
MaintenanceTaskStatusUpdate
```

Schema 字段必须与数据库字段保持一致，尤其是：

```text
manufacturer
product_series
device_type
document_type
fault_type
trace_id
references
retrieved_chunks
```

---

## 15. Repository 层要求

Repository 层负责数据库操作。

### 15.1 KnowledgeRepository

必须支持：

```text
create_document
update_document
get_document
list_documents
delete_document
create_chunks
list_chunks_by_document
delete_chunks_by_document
search_chunks
```

`search_chunks` 必须支持：

```text
query
manufacturer
product_series
device_type
document_type
top_k
```

并且只检索：

```text
knowledge_documents.parse_status = parsed
knowledge_documents.status = active
knowledge_chunks.status = active
```

---

### 15.2 RecordRepository

必须支持：

```text
create_qa_record
list_qa_records
create_diagnosis_record
list_diagnosis_records
```

---

### 15.3 MaintenanceRepository

必须支持：

```text
create_task
list_tasks
get_task
update_task_status
update_task
```

---

## 16. 迁移策略

### 16.1 当前阶段建议迁移任务

如果现有代码中尚未包含以下字段，应单独创建一个 migration：

```text
manufacturer
product_series
model
fault_type
alarm_code
retrieved_chunks
source_trace_id
```

尤其需要检查：

```text
knowledge_documents 是否有 manufacturer 和 product_series
knowledge_chunks 是否有 manufacturer 和 product_series
qa_records 是否有 manufacturer、product_series、retrieved_chunks
diagnosis_records 是否有 manufacturer、product_series、references
maintenance_tasks 是否有 manufacturer、product_series、source_trace_id
```

这些字段是收敛到华为/阳光逆变器场景后的关键字段。

---

### 16.2 迁移文件命名建议

```text
YYYYMMDDHHMM_add_inverter_domain_fields.py
```

例如：

```text
202605270001_add_inverter_domain_fields.py
```

---

### 16.3 Alembic 验收命令

```bash
cd backend
alembic -c alembic.ini upgrade head
```

或使用 uv：

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

必须真实连接 PostgreSQL 执行成功，不能只做离线 SQL 生成。

---

## 17. 数据一致性要求

### 17.1 文档与切片一致性

每个 `knowledge_documents.chunk_count` 必须等于对应 `knowledge_chunks` 数量。

上传成功后应满足：

```sql
SELECT chunk_count FROM knowledge_documents WHERE id = :document_id;
SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = :document_id;
```

两个结果必须一致。

---

### 17.2 parse_status 一致性

| 场景 | parse_status | chunk_count | error_message |
|---|---|---:|---|
| 上传未解析 | pending | 0 | null |
| 正在解析 | processing | 0 或已有旧值 | null |
| 解析成功 | parsed | >0 | null |
| 解析失败 | failed | 0 | 非空 |

---

### 17.3 references 真实性

`qa_records.references` 中的每条来源必须对应真实 `knowledge_chunks` 和 `knowledge_documents`。

禁止：

```text
编造 document_title
编造 page_number
编造 source
编造 chunk_index
```

无检索结果时：

```json
{
  "references": [],
  "retrieved_chunks": []
}
```

---

## 18. 第一版示例数据要求

第一版至少准备以下样例数据：

### 18.1 华为样例文档

```text
manufacturer = huawei
product_series = SUN2000
device_type = pv_inverter
document_type = manual / alarm_code / sop
```

样例主题：

```text
SUN2000 逆变器绝缘阻抗低排查
SUN2000 通信中断排查
FusionSolar 告警信息查看
```

### 18.2 阳光电源样例文档

```text
manufacturer = sungrow
product_series = SG
device_type = pv_inverter
document_type = manual / alarm_code / sop
```

样例主题：

```text
SG 系列逆变器过温降额处理
SG 系列交流过压处理
SG 系列 MPPT 异常与功率偏低排查
```

---

## 19. 第一版验收用 SQL 查询

### 19.1 检查文档数量

```sql
SELECT manufacturer, product_series, document_type, COUNT(*)
FROM knowledge_documents
GROUP BY manufacturer, product_series, document_type;
```

### 19.2 检查切片数量

```sql
SELECT d.manufacturer, d.product_series, COUNT(c.id) AS chunk_count
FROM knowledge_documents d
LEFT JOIN knowledge_chunks c ON c.document_id = d.id
GROUP BY d.manufacturer, d.product_series;
```

### 19.3 检查已解析文档

```sql
SELECT id, title, manufacturer, product_series, parse_status, chunk_count
FROM knowledge_documents
WHERE parse_status = 'parsed';
```

### 19.4 检查问答记录

```sql
SELECT trace_id, question, manufacturer, product_series, confidence, created_at
FROM qa_records
ORDER BY created_at DESC
LIMIT 20;
```

### 19.5 检查任务记录

```sql
SELECT title, manufacturer, product_series, fault_type, priority, task_status
FROM maintenance_tasks
ORDER BY created_at DESC
LIMIT 20;
```

---

## 20. 第一版数据库验收标准

第一版数据库验收必须真实执行，不允许只做静态检查。

### 20.1 PostgreSQL 连接验收

必须通过：

```bash
uv run alembic -c alembic.ini upgrade head
```

并确认没有连接超时、字段重复、迁移链断裂等问题。

---

### 20.2 知识库入库验收

上传一份华为或阳光逆变器样例文档后必须满足：

```text
1. knowledge_documents 新增记录
2. manufacturer 正确
3. product_series 正确
4. device_type = pv_inverter
5. parse_status = parsed
6. chunk_count > 0
7. knowledge_chunks 中存在真实 content
```

---

### 20.3 检索问答验收

调用：

```http
POST /api/retrieval/query
```

问题示例：

```text
华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？
阳光 SG 系列逆变器过温降额怎么处理？
```

必须满足：

```text
1. retrieved_chunks 不为空
2. references 不为空
3. references 来自真实 knowledge_chunks
4. qa_records 写入成功
5. trace_id 可追溯
6. answer 不是固定模拟模板
```

---

### 20.4 故障诊断验收

调用：

```http
POST /api/diagnosis/analyze
```

必须满足：

```text
1. diagnosis_records 写入成功
2. possible_causes 不为空
3. inspection_steps 不为空
4. safety_notes 不为空
5. trace_id 可追溯
```

---

### 20.5 检修任务验收

调用：

```http
POST /api/maintenance/tasks
```

必须满足：

```text
1. maintenance_tasks 写入成功
2. task_status = pending
3. manufacturer / product_series / device_type 保存正确
4. 可更新为 in_progress / completed
```

---

## 21. 禁止事项

数据库设计和开发中禁止：

```text
1. 使用 SQLite 作为正式数据库
2. 使用中文表名或拼音字段名
3. 在代码中写死数据库连接
4. 让 API 层直接操作数据库
5. 伪造 references
6. 只做内存模拟不写入 PostgreSQL
7. 用 Docker 作为正式部署数据库路线
8. 将 Intelligent-Teaching 的数据库作为正式依赖
9. 将 Energy-Maintenance 表写入其他项目数据库
10. 将光伏逆变器场景扩散到泛新能源设备
```

---

## 22. 与前两份文档的关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
```

其中：

- `01` 确定产品范围和功能边界；
- `02` 确定技术栈和架构约束；
- `03` 将产品范围落实为数据库表、字段、枚举、索引和验收标准。

后续文档如 API、前端页面、知识库处理、RAG 问答、测试验收都必须与本文档字段保持一致。

---

## 23. 下一步建议

本文档确认后，后续应继续编写：

```text
04_api_contract_design.md
05_frontend_page_and_interaction_spec.md
06_knowledge_base_and_document_processing_spec.md
07_retrieval_qa_and_fault_diagnosis_spec.md
09_testing_acceptance_and_quality_spec.md
10_vibe_coding_task_plan.md
```

在进入下一轮代码开发前，应先检查现有数据库模型是否与本文档一致，尤其是：

```text
manufacturer
product_series
device_type = pv_inverter
document_type = alarm_code
retrieved_chunks
source_trace_id
```

如不一致，应以“小任务制”单独修正，而不是在大阶段中混合修改多个模块。
---

## Task 02A 数据库设计一致性补充

本补充只定义数据库设计方向，不代表本轮已修改 SQLAlchemy model 或 Alembic migration。实际字段和表结构变更应进入后续 Task 02B。

### A. P0 核心数据对象

第一版本 P0 需要覆盖以下对象：

- users：基础用户、角色、状态、密码哈希预留。
- devices：光伏逆变器设备台账。
- device_maintenance_records：设备历史检修记录。
- uploaded_media：故障图片、上传资料附件与解析来源文件。
- knowledge_documents：知识文档元数据、审核状态、解析状态。
- knowledge_chunks：真实知识切片、来源追溯字段。
- qa_records：检修问答记录、references、retrieved_chunks、trace_id。
- diagnosis_records：故障诊断记录、设备关联、检修历史关联、references、safety_notes。
- maintenance_tasks：检修任务、来源类型、来源 trace。
- knowledge_contributions：知识贡献记录。
- knowledge_review_records：知识审核记录。
- model_output_corrections：模型输出纠错记录。
- sop_templates：SOP 模板。
- sop_execution_records：SOP 执行记录。
- operation_logs：操作日志。
- model_call_logs：模型调用日志。

### B. 关键字段一致性要求

下列字段需要在相关表、Pydantic schema、API 响应和前端类型中保持一致：

- manufacturer。
- product_series。
- model。
- device_type，第一版本前端和新增业务逻辑优先使用 `pv_inverter`。
- document_type。
- fault_type。
- alarm_code。
- trace_id。
- references。
- retrieved_chunks。
- source_trace_id。
- review_status、submitted_by、reviewed_by。
- provider、model_name、prompt、response、latency、success、error_message。

### C. JSONB 建议

PostgreSQL 中以下字段建议使用 JSONB：

- references。
- retrieved_chunks。
- suggested_steps。
- possible_causes。
- inspection_steps。
- safety_notes。
- recommended_actions。
- metadata_json。
- related_history。
- request_payload。
- response_payload。

### D. Task 02B 迁移方向

Task 02B 应基于现有迁移链继续新增 migration，不应重置迁移链。优先补齐缺失表，再补齐现有表字段，确保 SQLAlchemy model、Pydantic schema、repository、service、API、frontend 类型同步更新。
---

## Task 02B 数据库模型增强结果

Task 02B 已将 Task 02A 审查中提出的缺失表和关键字段落实到 SQLAlchemy model、Pydantic schema 和 Alembic migration。

### A. 新增表

- uploaded_media。
- device_maintenance_records。
- knowledge_contributions。
- knowledge_review_records。
- model_output_corrections。
- sop_templates。
- sop_execution_records。

### B. 已增强的已有表

- users：新增 password_hash、last_login_at。
- devices：新增 device_code、commissioning_date、last_fault_at、last_maintenance_at、fault_count、maintenance_count。
- knowledge_documents：新增 source_type、review_status、submitted_by、reviewed_by、reviewed_at、review_comment。
- knowledge_chunks：新增 content_hash。
- qa_records：新增 device_id、safety_notes、related_history、model_provider、model_name、created_by。
- diagnosis_records：新增 device_id、related_history、media_ids、model_provider、model_name、created_by。
- maintenance_tasks：新增 status、assignee_id、sop_template_id、sop_execution_id、root_cause、repair_action、replaced_parts、verification_result、is_recurrent、completed_by、created_by。
- model_call_logs：新增 call_type、prompt、response、latency_ms、success、created_by。

### C. 迁移文件

新增 Alembic migration：

```text
backend/alembic/versions/20260601_0002_enhance_schema_for_v2_requirements.py
```

本轮未连接真实 PostgreSQL，未执行 `alembic upgrade head`。真实数据库迁移验证应在 Task 03 执行。

---

## Task 18C Knowledge Graph Tables

Task 18C adds a PostgreSQL-backed knowledge graph foundation through migration:

```text
backend/alembic/versions/20260601_0003_add_knowledge_graph_tables.py
```

New graph tables:

- `kg_nodes`: normalized graph nodes for Huawei/Sungrow PV inverter manufacturers, product series, faults, alarms, components, causes, actions, tools, safety risks, documents, chunks, maintenance records, and field contributions.
- `kg_edges`: typed relations between graph nodes.
- `kg_node_aliases`: node aliases and normalized aliases for matching.
- `kg_evidence_links`: source-traceable evidence from nodes/edges back to documents, chunks, contributions, diagnosis records, tasks, maintenance records, and media.
- `kg_extraction_runs`: rule-based graph extraction run records.
- `kg_candidates`: pending node, edge, and alias candidates that require expert/admin approval.

The graph foundation stays inside PostgreSQL. Neo4j, NebulaGraph, JanusGraph, MongoDB, Elasticsearch, pgvector, embedding, OCR, and real LLM extraction remain deferred.
