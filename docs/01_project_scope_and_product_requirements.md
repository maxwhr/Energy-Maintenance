# 01 Project Scope and Product Requirements

> Document Name: `01_project_scope_and_product_requirements.md`  
> Project: `Energy-Maintenance`  
> Version: `v1.0`  
> Status: Product Baseline  
> Scope: Huawei and Sungrow PV Inverter Maintenance Knowledge Retrieval and Work Assistance System  
> Last Updated: 2026-05-27

---

## 1. 文档目的

本文档用于确定 `Energy-Maintenance` 项目的第一版产品边界、核心业务需求、功能范围、典型故障场景、用户角色、业务流程和验收标准。

本项目采用高标准 vibe coding 开发路线。本文档不是泛泛的需求描述，而是后续 AI 编码、接口设计、数据库设计、前端页面设计、测试验收和部署实施的产品基线。后续所有开发任务都必须以本文档为准，避免项目在开发过程中发散为泛新能源设备平台、通用知识库系统或普通聊天系统。

本文档解决以下问题：

1. 项目第一版到底做什么。
2. 项目第一版明确不做什么。
3. 系统面向哪些厂家、设备和故障类型。
4. 系统需要形成怎样的业务闭环。
5. 后续开发如何判断是否真正完成，而不是只完成雏形。

---

## 2. 项目基本信息

### 2.1 项目名称

英文名称：

```text
Energy-Maintenance
```

中文名称建议：

```text
光伏逆变器检修知识检索与作业辅助系统
```

完整定位表述：

```text
Energy-Maintenance 是面向华为与阳光电源光伏逆变器检修场景的知识检索与作业辅助系统。
系统以国产光伏逆变器运维资料为知识基础，通过文档解析、知识切片、检索问答、故障辅助诊断、检修任务管理和记录追溯，辅助运维人员完成告警排查、故障定位和作业过程规范化。
```

### 2.2 第一版项目定位

第一版聚焦：

```text
国产光伏逆变器检修知识检索与作业辅助
```

第一版重点支持两大厂家：

| 厂家编码 | 厂家名称 | 重点体系 / 系列 |
|---|---|---|
| `huawei` | 华为 | `SUN2000` / `FusionSolar` 体系 |
| `sungrow` | 阳光电源 | `SG` 系列光伏逆变器 |

第一版设备类型固定为：

| 设备类型编码 | 中文名称 | 是否第一版主线 |
|---|---|---|
| `pv_inverter` | 光伏逆变器 | 是 |

第一版不把储能电池系统、箱式变压器、电力巡检设备作为核心开发对象。这些内容可作为后续扩展方向，但不得进入第一版主线需求。

---

## 3. 项目范围边界

### 3.1 第一版必须聚焦的范围

第一版只围绕以下范围展开：

```text
厂家：华为、阳光电源
设备：光伏逆变器
资料：公开手册、告警说明、检修规程、故障案例、巡检规范、模拟检修记录
场景：告警排查、故障诊断、知识问答、作业辅助、记录追溯
```

### 3.2 第一版不得扩展的范围

第一版不得主动扩展到以下方向：

```text
泛新能源设备检修
储能电池系统完整运维
箱式变压器完整检修
电力巡检设备管理
风电设备检修
通用工业设备维修
车辆维修 / 摩托车维修 / 发动机检修
教育平台
通用客服机器人
通用企业知识库系统
```

如果已有代码、文档或页面中出现上述过宽表述，应在后续范围收敛任务中逐步改为“华为与阳光电源光伏逆变器检修”。

### 3.3 允许保留的扩展预留

第一版可以在数据库或接口中保留扩展字段，但不得让页面和核心流程变成泛化系统。

允许预留：

```text
manufacturer 字段
product_series 字段
device_type 字段
document_type 字段
embedding_status 字段
metadata_json 字段
```

不允许在第一版中把过多设备作为默认选项展示。

---

## 4. 核心痛点分析

### 4.1 运维人员面临的问题

光伏逆变器是光伏电站能量转换和并网控制的关键设备。现场运维人员在处理逆变器故障时通常面临以下问题：

1. 告警代码含义不清楚，需要在不同厂家手册中查找。
2. 华为和阳光电源的手册体系、术语、产品系列不同，资料检索效率低。
3. 逆变器故障现象与原因之间不是一一对应，需要结合设备状态、告警信息和现场检测综合判断。
4. 绝缘阻抗低、交流过压、过温、通信中断等问题具有较强现场排查要求，经验不足时容易漏查。
5. 手册中有大量安全注意事项，现场人员可能忽视停电、验电、防护、接地等操作要求。
6. 传统问答容易给出泛泛建议，缺少资料来源，无法追溯。
7. 故障处理过程缺少结构化记录，不便后续复盘和沉淀。
8. 一些逆变器异常不会立即停机，但会导致降额、MPPT 异常和发电量偏低，属于隐性损失问题。

### 4.2 系统要解决的核心问题

`Energy-Maintenance` 第一版要解决以下核心问题：

| 问题 | 系统解决方式 |
|---|---|
| 资料分散 | 将华为、阳光电源逆变器资料统一上传、解析、切片、入库 |
| 检索低效 | 基于厂家、系列、文档类型、关键词进行知识切片检索 |
| 告警难理解 | 提供告警解释、可能原因、排查步骤和处理建议 |
| 现场排查不规范 | 输出结构化检修步骤和安全注意事项 |
| 回答不可追溯 | 每个回答返回真实 references 和 retrieved_chunks |
| 处理过程不可沉淀 | 保存 qa_records、diagnosis_records 和 maintenance_tasks |
| 后续扩展困难 | 通过标准数据模型和接口契约预留 RAG、pgvector、大模型能力 |

---

## 5. 第一版典型故障范围

第一版必须围绕光伏逆变器常见、高频、可知识化的故障类型展开。

### 5.1 必须支持的故障类型

| 故障类型编码 | 中文名称 | 说明 |
|---|---|---|
| `low_insulation_resistance` | 绝缘阻抗低 | 涉及组件、电缆、接地、直流侧绝缘检测 |
| `dc_abnormal` | 直流侧异常 | 包括组串电压异常、直流输入异常、接线异常等 |
| `ac_overvoltage` | 交流过压 | 涉及电网电压、并网点、保护参数等 |
| `ac_undervoltage` | 交流欠压 | 涉及电网侧异常、接线、保护动作等 |
| `grid_connection_fault` | 并网异常 | 包括并网失败、频率异常、电网参数异常等 |
| `over_temperature` | 逆变器过温 | 涉及散热、风道、环境温度、降额运行 |
| `fan_fault` | 风扇异常 | 涉及风扇堵转、损坏、散热性能下降 |
| `communication_interruption` | 通信中断 | 涉及 FusionSolar、数据采集器、网络、RS485/以太网等 |
| `device_offline` | 设备离线 | 需要区分真实停机和通信离线 |
| `mppt_abnormal` | MPPT 异常 | 涉及组串失配、遮挡、输入异常、功率跟踪异常 |
| `low_power_generation` | 功率偏低 / 发电量异常 | 涉及隐性损失、降额、组串异常、环境因素 |
| `alarm_code_query` | 告警代码查询 | 根据手册和告警说明解释告警含义和处理建议 |

### 5.2 第一版暂不重点支持的故障类型

以下内容第一版可以预留，但不作为核心验收重点：

```text
板级硬件维修
功率模块级拆修
控制板更换指导
逆变器内部电路级维修
储能 PCS 深度诊断
BMS 热失控分析
箱式变压器完整保护逻辑
```

原因：这些内容通常依赖厂商内部售后资料、现场资质和强电安全规范，不适合作为第一版公开知识库系统的主线。

---

## 6. 用户角色

第一版不要求实现复杂权限系统，但产品设计中需要明确潜在用户角色。

### 6.1 管理员 `admin`

职责：

```text
管理知识库资料
查看系统状态
维护基础数据
查看问答、诊断和任务记录
```

第一版权限要求：

```text
可以先不实现完整登录鉴权，但用户表和角色字段需要预留。
```

### 6.2 运维工程师 `engineer`

职责：

```text
上传或查阅逆变器资料
发起检修问答
发起故障诊断
创建和处理检修任务
查看历史记录
```

### 6.3 现场操作人员 `operator`

职责：

```text
根据告警现象查询排查步骤
查看安全注意事项
填写处理结果
提交检修记录
```

### 6.4 只读查看人员 `viewer`

职责：

```text
查看知识库、任务和记录
不进行写操作
```

第一版可以只实现静态用户或无鉴权访问，但数据库设计应保留 `users` 表和 `role` 字段。

---

## 7. 第一版核心业务流程

### 7.1 知识库入库流程

```text
上传华为 / 阳光电源逆变器资料
        ↓
保存原始文件
        ↓
解析 txt / md / pdf / docx 文本
        ↓
清洗文本
        ↓
按 chunk_size 和 overlap 切片
        ↓
写入 knowledge_documents
        ↓
写入 knowledge_chunks
        ↓
更新 parse_status、chunk_count、page_count、parsed_at
        ↓
前端展示文档和切片
```

### 7.2 检修知识问答流程

```text
用户输入逆变器检修问题
        ↓
选择厂家 huawei / sungrow
        ↓
选择产品系列 SUN2000 / FusionSolar / SG
        ↓
选择文档类型 manual / alarm_code / sop / fault_case
        ↓
系统检索 knowledge_chunks
        ↓
返回 retrieved_chunks
        ↓
生成结构化 answer 和 suggested_steps
        ↓
返回 references、confidence、trace_id
        ↓
保存 qa_records
```

### 7.3 故障辅助诊断流程

```text
用户输入厂家、产品系列、告警代码、故障现象、设备状态
        ↓
系统识别故障类型
        ↓
检索相关知识片段
        ↓
生成可能原因、排查步骤、安全注意事项、处理建议
        ↓
返回 references、confidence、trace_id
        ↓
保存 diagnosis_records
```

### 7.4 检修任务流转流程

```text
用户根据问答或诊断结果创建检修任务
        ↓
填写任务标题、设备信息、故障描述、优先级、负责人
        ↓
任务状态 pending
        ↓
现场处理后更新为 in_progress / completed / cancelled
        ↓
填写处理结果摘要
        ↓
保存任务记录
```

### 7.5 记录追溯流程

```text
每次问答生成 trace_id
每次诊断生成 trace_id
每个检修任务保存处理过程
所有 references 指向真实 knowledge_chunks
用户可以在记录中心查询历史问答、诊断和任务
```

---

## 8. 第一版页面需求

第一版建议包含以下页面。

| 页面名称 | 路由建议 | 主要功能 |
|---|---|---|
| DashboardView | `/dashboard` | 系统首页、统计卡片、核心入口 |
| KnowledgeBaseView | `/knowledge` | 文档上传、解析状态、切片查看 |
| RetrievalChatView | `/retrieval` | 检修知识问答、来源追溯 |
| FaultDiagnosisView | `/diagnosis` | 故障辅助诊断、排查建议 |
| MaintenanceTaskView | `/tasks` | 检修任务创建、列表、状态更新 |
| RecordCenterView / Trace | `/trace` | 问答记录、诊断记录、任务记录追溯 |
| SystemStatusView | `/system` | 后端状态、数据库状态、知识库统计 |

当前前端以 `/trace` 作为记录追溯入口，并通过 record-center 接口查询 QA、诊断、任务和相关业务记录。

---

## 9. 第一版功能需求

### 9.1 Dashboard 系统首页

必须展示：

```text
系统名称
项目定位
支持厂家：华为、阳光电源
支持设备：光伏逆变器
知识库文档数量
知识切片数量
问答记录数量
诊断记录数量
检修任务数量
系统运行状态
核心模块入口
```

验收标准：

1. 页面文案不再泛化为“新能源设备全场景”。
2. 明确展示华为、阳光电源、光伏逆变器。
3. 统计数据优先来自后端接口，不应长期写死。

### 9.2 知识库管理

必须支持：

```text
上传 txt / md / pdf / docx
填写厂家 manufacturer
填写产品系列 product_series
填写设备类型 device_type = pv_inverter
填写文档类型 document_type
填写来源 source
填写摘要 summary
显示 parse_status
显示 chunk_count
查看知识切片
```

厂家选项：

```text
huawei：华为
sungrow：阳光电源
```

产品系列选项：

```text
SUN2000
FusionSolar
SG
```

文档类型选项：

```text
manual：设备手册
alarm_code：告警代码
sop：检修规程
fault_case：故障案例
inspection_standard：巡检规范
maintenance_record：检修记录
```

验收标准：

1. 上传样例 txt 后 `parse_status = parsed`。
2. `chunk_count > 0`。
3. `knowledge_chunks` 中有真实内容。
4. 不支持文件类型返回明确错误。
5. 空文件返回明确错误。
6. 文件不会保存到前端目录。

### 9.3 检修知识问答

必须支持：

```text
输入问题
选择厂家
选择产品系列
选择文档类型
设置 top_k
调用 /api/retrieval/query
展示 answer
展示 suggested_steps
展示 references
展示 retrieved_chunks
展示 confidence
展示 trace_id
保存 qa_records
```

检索问答不能只返回固定模拟回答。

验收标准：

1. 上传华为或阳光电源逆变器资料后，提问能检索到真实切片。
2. references 不为空。
3. references 必须来自真实 `knowledge_chunks`。
4. answer 不得编造不存在的文档标题、页码或来源。
5. 每次问答必须保存 `qa_records`。
6. `GET /api/retrieval/records` 或记录中心接口能查到刚才的问答。

### 9.4 故障辅助诊断

必须支持输入：

```text
manufacturer
product_series
fault_type
alarm_code
fault_description
device_status
```

必须输出：

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

第一版可以采用规则型诊断逻辑，但必须围绕光伏逆变器常见故障，不得泛化为所有设备。

验收标准：

1. 输入“华为 SUN2000 绝缘阻抗低告警”能返回绝缘排查流程。
2. 输入“阳光 SG 逆变器过温”能返回散热、风扇、环境温度等排查建议。
3. 诊断结果保存到 `diagnosis_records`。
4. 如有知识库命中，references 来自真实知识片段。

### 9.5 检修任务管理

必须支持：

```text
创建任务
查看任务列表
查看任务详情
更新任务状态
填写处理结果摘要
```

任务字段应包括：

```text
title
manufacturer
product_series
device_type
fault_type
fault_description
priority
task_status
assignee
due_date
result_summary
```

任务状态：

```text
pending
in_progress
completed
cancelled
```

优先级：

```text
low
medium
high
critical
```

验收标准：

1. 创建任务后刷新页面数据不丢失。
2. 状态更新写入 PostgreSQL。
3. 任务详情能看到厂家、系列、故障描述和处理结果。

### 9.6 记录追溯中心

必须支持：

```text
查看 qa_records
查看 diagnosis_records
查看 maintenance_tasks
按 trace_id 查询
按厂家 / 产品系列 / 故障类型筛选
```

第一版如果时间有限，可以先实现后端接口，再补前端页面。

验收标准：

1. 问答记录真实入库。
2. 诊断记录真实入库。
3. trace_id 可用于关联一次问答或诊断。
4. references 和 suggested_steps 可在记录中查看。

### 9.7 系统状态页

必须展示：

```text
后端运行状态
数据库连接状态
当前环境
当前版本
知识库文档数量
知识切片数量
问答记录数量
诊断记录数量
```

验收标准：

1. 数据库未连接时显示明确异常，不应页面崩溃。
2. 数据库连接正常时显示统计数据。
3. 状态页不只显示静态文本。

---

## 10. 数据需求概览

第一版核心数据对象：

| 数据对象 | 说明 |
|---|---|
| `knowledge_documents` | 逆变器资料文档元数据 |
| `knowledge_chunks` | 文档解析后的知识片段 |
| `qa_records` | 检修问答记录 |
| `diagnosis_records` | 故障诊断记录 |
| `maintenance_tasks` | 检修任务 |
| `users` | 用户与角色预留 |
| `devices` | 设备台账预留，可后续增强 |

关键业务字段：

```text
manufacturer：huawei / sungrow
product_series：SUN2000 / FusionSolar / SG
device_type：pv_inverter
document_type：manual / alarm_code / sop / fault_case / inspection_standard / maintenance_record
fault_type：low_insulation_resistance / over_temperature / communication_interruption 等
trace_id：问答或诊断追溯编号
```

---

## 11. 非功能需求

### 11.1 可追溯性

系统必须保证：

```text
回答有来源
诊断有记录
任务有状态
历史可查询
```

所有问答和诊断都应保存 `trace_id`。

### 11.2 可维护性

后端必须分层：

```text
API 层只处理请求响应
Service 层处理业务逻辑
Repository 层处理数据库访问
Knowledge 层处理文档解析
RAG 层处理检索和回答生成
```

不得把核心业务逻辑全部写在 API 文件中。

### 11.3 可部署性

最终部署必须面向：

```text
LoongArch + Kylin
Python virtual environment
PostgreSQL native service
systemd
Nginx
```

不得把 Docker 作为 Energy-Maintenance 的正式部署路线。

### 11.4 兼容性

考虑龙芯服务器部署，依赖选择应尽量稳健：

```text
PDF 解析优先 pypdf
DOCX 解析使用 python-docx
避免依赖复杂原生编译库作为第一版必需能力
embedding、pgvector、大模型能力后续再增强
```

---

## 12. 第一版必须完成的业务闭环

第一版是否合格，以以下闭环是否真实跑通为核心判断。

### 12.1 知识库闭环

```text
上传华为或阳光电源逆变器资料
        ↓
解析成功
        ↓
生成知识切片
        ↓
写入 PostgreSQL
        ↓
前端可查看文档和切片
```

验收条件：

```text
parse_status = parsed
chunk_count > 0
knowledge_chunks 有真实内容
```

### 12.2 检索问答闭环

```text
用户提出逆变器故障问题
        ↓
系统检索真实 knowledge_chunks
        ↓
返回 answer、references、retrieved_chunks
        ↓
保存 qa_records
        ↓
记录中心可查询
```

验收条件：

```text
references 不为空
retrieved_chunks 不为空
qa_records 写入成功
answer 基于真实切片
```

### 12.3 故障诊断闭环

```text
用户输入厂家、系列、告警、故障现象
        ↓
系统输出可能原因、排查步骤、安全注意事项、处理建议
        ↓
保存 diagnosis_records
        ↓
可追溯查询
```

验收条件：

```text
diagnosis_records 写入成功
trace_id 存在
安全注意事项不为空
```

### 12.4 检修任务闭环

```text
用户创建检修任务
        ↓
任务状态 pending
        ↓
更新为 in_progress / completed
        ↓
填写处理结果
        ↓
任务记录可追溯
```

验收条件：

```text
maintenance_tasks 写入成功
状态更新成功
刷新后数据不丢失
```

---

## 13. 增强功能规划

以下功能属于后续增强，不作为第一版必须完成项。

### 13.1 pgvector 与 embedding

后续增强：

```text
为 knowledge_chunks 增加 embedding 字段
启用 PostgreSQL pgvector 扩展
实现向量检索
实现关键词 + 向量混合检索
```

### 13.2 大模型回答生成

后续增强：

```text
接入 LLM client
基于 retrieved_chunks 构造 prompt
生成更自然的检修回答
保留 references 和 trace_id
```

### 13.3 OCR 与多模态

后续增强：

```text
告警截图 OCR
扫描版 PDF OCR
设备铭牌识别
逆变器照片辅助描述
```

### 13.4 权限系统

后续增强：

```text
登录认证
角色权限
管理员 / 工程师 / 操作员 / 只读用户
```

### 13.5 检修报告导出

后续增强：

```text
问答记录导出
诊断结果导出
检修任务报告导出
PDF / Word 格式报告
```

---

## 14. 第一版暂不做内容

第一版明确不做：

```text
完整储能电池系统诊断
箱式变压器完整检修体系
电力巡检设备管理
真实 OCR
真实大模型接入
真实 embedding
pgvector
复杂权限系统
Docker 部署
多租户
IoT 实时监控
移动端适配
板级硬件维修指导
```

如果后续 Codex 生成这些功能，应视为范围偏移。

---

## 15. 样例资料准备要求

为确保系统演示真实可靠，第一版应准备以下样例资料。

### 15.1 华为方向

```text
Huawei SUN2000 用户手册节选
FusionSolar 运维说明节选
华为逆变器告警代码样例
华为逆变器绝缘阻抗低排查流程
华为逆变器通信中断排查流程
```

### 15.2 阳光电源方向

```text
Sungrow SG 系列用户手册节选
阳光电源逆变器告警代码样例
阳光电源逆变器过温降额处理流程
阳光电源逆变器 MPPT 异常案例
阳光电源逆变器并网异常排查流程
```

### 15.3 人工整理专题文档

建议整理成 Markdown 或 txt：

```text
pv_inverter_low_insulation_resistance_troubleshooting.md
pv_inverter_over_temperature_troubleshooting.md
pv_inverter_communication_interruption_troubleshooting.md
pv_inverter_mppt_abnormal_case.md
pv_inverter_low_power_generation_case.md
```

文件内容必须围绕华为和阳光电源逆变器，不得写成泛泛电力设备知识。

---

## 16. 后续开发任务拆分原则

后续 vibe coding 必须采用小任务制。

每个任务应满足：

```text
目标单一
允许修改文件有限
必须包含执行命令
必须包含验收标准
必须说明是否真实执行成功
不得用静态检查冒充真实闭环
```

推荐任务顺序：

```text
Task 01：补充 manufacturer 和 product_series 字段
Task 02：统一前端厂家和系列筛选项
Task 03：打通 PostgreSQL 真实连接与 Alembic 迁移
Task 04：上传华为样例文档并验证 chunks 入库
Task 05：上传阳光样例文档并验证 chunks 入库
Task 06：检索问答真实闭环验收
Task 07：故障诊断结合知识库 references
Task 08：记录中心页面开发
Task 09：系统状态页增加数据库和知识库统计
Task 10：LoongArch + Kylin 原生部署准备
```

---

## 17. 第一版完成判定标准

第一版达到可交付标准，必须满足：

1. PostgreSQL 能真实连接。
2. Alembic 能真实执行 `upgrade head`。
3. 能上传华为或阳光电源逆变器样例文档。
4. 能生成真实 `knowledge_chunks`。
5. 能基于真实切片完成检修问答。
6. 问答结果包含真实 references。
7. 问答记录写入 `qa_records`。
8. 故障诊断结果写入 `diagnosis_records`。
9. 检修任务写入 `maintenance_tasks`。
10. 前端页面能完成知识库、问答、诊断、任务、记录、状态等核心操作。
11. 页面文案和筛选项聚焦华为、阳光电源、光伏逆变器。
12. README 和 AGENTS.md 明确禁止泛化到其他设备与 Docker 部署路线。
13. 没有伪造验收结果。
14. 没有把 references 编造成不存在的资料来源。

---

## 18. 文档结论

`Energy-Maintenance` 第一版不是泛新能源设备系统，而是面向华为与阳光电源光伏逆变器检修场景的知识检索与作业辅助系统。

第一版核心目标是跑通以下闭环：

```text
逆变器资料上传
    ↓
文本解析与知识切片
    ↓
PostgreSQL 入库
    ↓
基于切片的检修问答
    ↓
真实 references 追溯
    ↓
故障诊断与检修任务
    ↓
记录沉淀与系统状态展示
```

后续所有开发、测试和验收都必须围绕该闭环展开。
