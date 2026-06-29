# 07 检索问答与故障诊断规格文档

**Document Name:** `07_retrieval_qa_and_fault_diagnosis_spec.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Core Scenario:** Huawei / Sungrow PV Inverter Maintenance QA and Fault Diagnosis  
**Backend Stack:** FastAPI + PostgreSQL + SQLAlchemy  
**First Version Retrieval:** PostgreSQL keyword retrieval + rule-based answer generation  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版检索问答与故障诊断模块的设计标准，包括：

```text
1. 检索问答的输入、处理流程、输出结构
2. 中文关键词检索规则
3. 厂家、产品系列、设备类型和文档类型过滤规则
4. references 来源构建规则
5. 规则型回答生成规则
6. 故障辅助诊断规则
7. qa_records 与 diagnosis_records 保存要求
8. trace_id 追溯要求
9. 第一版验收标准
10. 后续 pgvector、embedding、大模型增强路线
```

本项目第一版已经明确收敛为：

> 面向华为与阳光电源光伏逆变器的检修知识检索与作业辅助系统。

因此，检索问答和故障诊断不应做成通用聊天机器人，也不应做成泛新能源设备问答系统。

第一版核心目标是：

```text
用户输入华为或阳光电源光伏逆变器检修问题
    ↓
系统从真实 knowledge_chunks 中检索相关资料
    ↓
生成结构化检修回答
    ↓
返回真实 references
    ↓
保存 qa_records
```

故障诊断核心目标是：

```text
用户输入故障现象、厂家、产品系列、故障类型、告警代码
    ↓
系统基于规则和知识库资料生成可能原因、排查步骤、安全注意事项、推荐处理措施
    ↓
保存 diagnosis_records
    ↓
可进一步生成检修任务
```

---

## 2. 第一版模块定位

### 2.1 检索问答模块定位

检索问答模块不是普通聊天系统，而是：

```text
光伏逆变器检修知识问答与来源追溯模块
```

核心能力：

```text
1. 接收检修问题
2. 根据厂家、产品系列、设备类型、文档类型过滤知识库
3. 检索真实 knowledge_chunks
4. 生成结构化回答
5. 返回 references 和 retrieved_chunks
6. 保存 qa_records
```

---

### 2.2 故障诊断模块定位

故障诊断模块不是自动替代工程师的维修决策系统，而是：

```text
检修辅助分析与标准化排查建议模块
```

它应提供：

```text
可能原因
排查步骤
安全注意事项
推荐处理措施
来源依据
追溯编号
```

不得承诺：

```text
百分百确定故障原因
替代现场安全判断
替代厂家售后诊断
自动远程修复设备
```

---

## 3. 第一版支持范围

### 3.1 支持厂家

| 值 | 中文名称 |
|---|---|
| huawei | 华为 |
| sungrow | 阳光电源 |

---

### 3.2 支持产品系列

| 厂家 | 产品系列 |
|---|---|
| huawei | SUN2000 |
| huawei | FusionSolar |
| sungrow | SG |

---

### 3.3 支持设备类型

第一版只支持：

| 值 | 中文名称 |
|---|---|
| pv_inverter | 光伏逆变器 |

不支持将第一版扩展为储能电池、箱式变压器、电力巡检设备或泛新能源设备诊断。

---

### 3.4 支持故障类型

| fault_type | 中文名称 | 典型问题 |
|---|---|---|
| low_insulation_resistance | 绝缘阻抗低 | 直流侧组串、电缆、接地、组件受潮 |
| dc_abnormal | 直流侧异常 | 直流输入异常、组串异常、接插件问题 |
| ac_overvoltage | 交流过压 | 电网电压过高、并网点异常 |
| ac_undervoltage | 交流欠压 | 电网电压过低、并网条件不满足 |
| grid_connection_fault | 并网异常 | 并网失败、频率/电压异常 |
| over_temperature | 逆变器过温 | 散热、风扇、环境温度、降额 |
| fan_fault | 风扇异常 | 风扇堵转、损坏、散热不足 |
| communication_interruption | 通信中断 | 网络、采集器、RS485、监控平台 |
| device_offline | 设备离线 | 设备停机、通信断链、平台离线 |
| mppt_abnormal | MPPT 异常 | 组串不一致、遮挡、跟踪异常 |
| low_power_generation | 功率偏低 | 隐性损失、降额、组串问题、污染遮挡 |
| alarm_code_query | 告警代码查询 | 告警码解释与处理建议 |

---

## 4. 检索问答接口

核心接口：

```http
POST /api/retrieval/query
```

---

### 4.1 请求字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|---|---|---:|---|---|
| query | string | 否 | null | 用户问题 |
| question | string | 否 | null | 兼容字段，与 query 至少一个非空 |
| manufacturer | string | 否 | null | huawei / sungrow |
| product_series | string | 否 | null | SUN2000 / FusionSolar / SG |
| device_type | string | 否 | pv_inverter | 光伏逆变器 |
| document_type | string | 否 | null | 文档类型 |
| top_k | integer | 否 | 5 | 检索返回数量，最大 10 |
| include_sources | boolean | 否 | true | 是否返回来源 |

---

### 4.2 请求校验规则

必须校验：

```text
1. query 和 question 至少一个非空
2. top_k 范围为 1 到 10
3. manufacturer 如填写，必须为 huawei 或 sungrow
4. device_type 如填写，第一版必须为 pv_inverter
5. document_type 如填写，必须在允许文档类型中
```

空问题返回：

```json
{
  "code": 400,
  "message": "query or question must not be empty",
  "data": null
}
```

top_k 超限返回：

```json
{
  "code": 400,
  "message": "top_k must be between 1 and 10",
  "data": null
}
```

---

### 4.3 处理流程

检索问答处理流程：

```text
1. 接收 query/question
2. 标准化问题
3. 提取检索关键词
4. 构造过滤条件
5. 查询 knowledge_chunks
6. 计算相关性分数
7. 按分数排序并取 top_k
8. 构造 references
9. 构造 retrieved_chunks
10. 生成规则型回答
11. 生成 suggested_steps
12. 生成 confidence
13. 生成 trace_id
14. 写入 qa_records
15. 返回结构化结果
```

---

## 5. 中文关键词检索规则

第一版不强制使用 embedding 和 pgvector，而是使用 PostgreSQL 文本字段和规则型关键词匹配。

### 5.1 为什么第一版先做关键词检索

原因：

```text
1. 实现稳定，便于快速打通真实闭环
2. 不依赖本地大模型和向量库
3. 更适合 LoongArch + Kylin 原生部署初期验证
4. 方便排查 references 是否真实来自 knowledge_chunks
5. 后续可以平滑升级为混合检索
```

---

### 5.2 查询标准化

对用户问题进行标准化：

```text
1. 去除首尾空白
2. 统一全角/半角符号
3. 英文转为大小写不敏感
4. 保留中文、英文缩写、数字、型号、告警码
5. 不删除 SUN2000、SG、MPPT、RS485、Modbus 等关键术语
```

示例：

```text
原问题：华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？
标准化：华为 SUN2000 逆变器 绝缘阻抗低 排查
```

---

### 5.3 中文关键词词典

第一版应内置领域关键词词典。

#### 厂家关键词

```text
华为 -> huawei
Huawei -> huawei
SUN2000 -> huawei / product_series SUN2000
FusionSolar -> huawei / product_series FusionSolar

阳光 -> sungrow
阳光电源 -> sungrow
Sungrow -> sungrow
SG -> sungrow / product_series SG
```

#### 设备关键词

```text
逆变器
光伏逆变器
并网逆变器
组串式逆变器
PV inverter
inverter
```

#### 故障关键词

```text
绝缘阻抗低
绝缘低
对地绝缘
接地异常
直流侧异常
组串异常
直流输入
交流过压
交流欠压
电网过压
电网欠压
并网异常
并网失败
过温
温度高
降额
风扇异常
散热异常
通信中断
设备离线
采集器异常
RS485
Modbus
MPPT
功率偏低
发电量低
告警码
故障码
报警
```

#### 排查动作关键词

```text
排查
检查
处理
原因
步骤
怎么做
如何处理
维修
检修
复位
恢复
安全注意
```

---

### 5.4 关键词扩展规则

当用户问题中出现某一故障词，应自动扩展相关词。

#### 绝缘阻抗低

输入包含：

```text
绝缘阻抗低
绝缘低
接地异常
```

扩展：

```text
绝缘阻抗
直流侧
组串
电缆
接地
组件受潮
对地绝缘
绝缘测试
```

#### 过温

输入包含：

```text
过温
温度高
降额
```

扩展：

```text
散热
风扇
风道
环境温度
降额运行
清理
通风
```

#### 通信中断

输入包含：

```text
通信中断
设备离线
平台离线
```

扩展：

```text
FusionSolar
采集器
RS485
Modbus
网络
数据上报
通讯
离线
```

#### MPPT 异常 / 功率偏低

输入包含：

```text
MPPT
功率偏低
发电量低
```

扩展：

```text
组串
遮挡
组件污染
直流输入
降额
跟踪异常
发电量异常
```

---

## 6. 检索过滤规则

检索必须基于真实数据库：

```text
knowledge_documents
knowledge_chunks
```

只允许检索：

```text
knowledge_documents.parse_status = parsed
knowledge_documents.status = active
knowledge_chunks.status = active
```

---

### 6.1 manufacturer 过滤

如用户指定：

```text
manufacturer = huawei
```

则只检索：

```text
knowledge_chunks.manufacturer = huawei
```

如未指定 manufacturer，可根据问题自动识别。

例如问题包含“华为”“SUN2000”，自动设置或提高 huawei 权重。

---

### 6.2 product_series 过滤

如用户指定：

```text
product_series = SUN2000
```

则优先检索该系列。

如果未指定，但 query 中包含：

```text
SUN2000
FusionSolar
SG
```

应用于排序加权。

---

### 6.3 device_type 过滤

第一版默认：

```text
device_type = pv_inverter
```

不要检索其他设备类型。

---

### 6.4 document_type 过滤

如果用户指定文档类型，则按类型过滤。

常见选择：

```text
manual
alarm_code
sop
fault_case
inspection_standard
maintenance_record
```

如果未指定，可全部检索，但排序时建议：

```text
alarm_code / sop / fault_case 权重略高于 manual
```

原因：

```text
问答和诊断通常更需要故障处理和检修流程，而不是完整手册中的泛化说明。
```

---

## 7. 相关性评分规则

第一版可采用可解释的规则型评分，不需要复杂模型。

### 7.1 基础评分因素

建议评分由以下因素组成：

```text
1. query 关键词命中 content
2. query 关键词命中 section_title
3. 厂家匹配
4. 产品系列匹配
5. 文档类型匹配
6. 故障类型关键词匹配
7. 内容长度合理性
8. 最近上传或高可信来源可轻微加权
```

---

### 7.2 简化评分公式

可使用如下思路：

```text
score =
  content_keyword_hits * 1.0
+ title_keyword_hits * 1.5
+ manufacturer_match * 2.0
+ product_series_match * 1.5
+ document_type_match * 1.0
+ fault_type_match * 2.0
+ source_weight
- length_penalty
```

然后归一化到：

```text
0.0 - 1.0
```

第一版不要求公式完全固定，但必须可解释。

---

### 7.3 排序规则

排序优先级：

```text
1. score 高的优先
2. 厂家匹配优先
3. 产品系列匹配优先
4. 故障类型匹配优先
5. 文档类型更贴近故障处理的优先
6. chunk_index 可作为稳定排序辅助
```

---

### 7.4 最低分过滤

分数过低的 chunk 不应返回。

建议：

```text
score <= 0 时不返回
```

如果所有结果都低于阈值：

```text
references = []
retrieved_chunks = []
```

不得为了凑数量返回无关片段。

---

## 8. retrieved_chunks 构建规则

`retrieved_chunks` 用于前端展示系统实际检索到的知识片段。

每个 retrieved_chunk 必须来自真实 `knowledge_chunks`。

字段：

```json
{
  "chunk_id": "chunk-001",
  "document_id": "doc-001",
  "document_title": "华为 SUN2000 逆变器告警排查样例",
  "manufacturer": "huawei",
  "product_series": "SUN2000",
  "device_type": "pv_inverter",
  "document_type": "alarm_code",
  "section_title": "绝缘阻抗低告警处理",
  "chunk_index": 0,
  "content": "当华为 SUN2000 逆变器出现绝缘阻抗低告警时...",
  "content_preview": "当华为 SUN2000 逆变器出现绝缘阻抗低告警时...",
  "score": 0.82
}
```

第一版可以只返回 `content_preview`，但建议保留完整 content 供前端折叠展示。

---

## 9. references 构建规则

references 是系统可信度和可追溯性的关键。

### 9.1 references 必须真实

每条 reference 必须来自真实：

```text
knowledge_chunks
knowledge_documents
```

不得编造：

```text
document_title
page_number
section_title
source
chunk_index
score
```

---

### 9.2 reference 字段

```json
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
```

---

### 9.3 无结果时的 references

如果检索不到相关内容：

```json
"references": []
```

禁止返回：

```text
参考来源：华为官方手册
参考来源：阳光电源手册
```

除非该来源确实来自已入库文档。

---

## 10. 规则型回答生成

第一版不强制接入真实大模型。

回答生成可以采用：

```text
检索片段摘要 + 故障类型模板 + 安全提示 + 建议步骤
```

但回答不能是完全固定模板，必须结合检索结果中的：

```text
厂家
产品系列
故障类型
retrieved_chunks 内容
document_type
```

---

### 10.1 回答结构

建议回答包含：

```text
1. 判断依据
2. 可能原因
3. 排查建议
4. 安全注意事项
5. 后续记录建议
```

---

### 10.2 回答示例：有检索结果

输入：

```text
华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？
```

输出示例：

```text
根据已入库的华为 SUN2000 光伏逆变器告警资料，系统检索到与“绝缘阻抗低”相关的处理内容。该类问题通常需要优先关注直流侧组串、电缆绝缘、接地状态以及组件受潮等因素。

建议先确认告警发生时间、关联组串和设备运行状态，再按照安全规程检查直流侧接插件、电缆绝缘和接地情况。必要时使用合规仪表检测绝缘阻抗，处理异常点后复位告警并持续观察是否再次触发。
```

---

### 10.3 回答示例：无检索结果

```text
当前知识库中未检索到足够相关的华为或阳光电源光伏逆变器资料。以下仅提供通用安全排查建议：请先确认设备厂家、产品系列、型号、告警代码和现场安全条件，再依据厂家手册进行处理。

建议补充上传对应厂家设备手册、告警代码表或检修规程后重新检索。
```

无检索结果时：

```text
confidence 应较低
references = []
retrieved_chunks = []
```

---

## 11. suggested_steps 生成规则

`suggested_steps` 用于输出可执行的检修步骤。

### 11.1 通用步骤骨架

```text
1. 确认现场安全条件
2. 查看告警代码、发生时间和设备状态
3. 根据故障类型检查相关部件
4. 按厂家手册执行处理
5. 恢复运行后观察告警是否消除
6. 保存检修记录和复检结果
```

---

### 11.2 不同故障类型步骤

#### 绝缘阻抗低

```text
1. 确认检修人员具备电气作业资质，并按规程做好停机或隔离措施。
2. 查看逆变器告警代码、发生时间和关联组串。
3. 检查直流侧组串、电缆、接插件和接地情况。
4. 检查组件是否破损、受潮或存在明显污染。
5. 使用合规仪表检测绝缘阻抗。
6. 处理异常点后恢复运行并观察告警是否消除。
7. 记录检测数值、处理过程和复检结论。
```

#### 过温 / 风扇异常

```text
1. 查看逆变器温度、告警时间和是否发生降额。
2. 检查进风口、出风口和散热通道是否堵塞。
3. 检查风扇运行状态、转速和异常噪声。
4. 清理灰尘、杂物和遮挡物。
5. 核对环境温度和安装通风条件。
6. 处理后观察温度和功率是否恢复。
```

#### 通信中断 / 设备离线

```text
1. 判断是设备停机还是监控平台通信中断。
2. 检查 FusionSolar 或监控平台上的离线时间和设备状态。
3. 检查采集器、电源、网络和数据上报状态。
4. 检查 RS485、网线或通信模块连接。
5. 必要时重启通信设备或重新配置通信参数。
6. 恢复后确认数据是否正常上报。
```

#### MPPT 异常 / 功率偏低

```text
1. 对比同区域、同型号逆变器的发电功率。
2. 检查各 MPPT 支路电压、电流是否明显不一致。
3. 检查组串遮挡、组件污染、接线松动和直流输入异常。
4. 查看是否存在过温降额或电网限制导致功率下降。
5. 清理组件或处理异常组串后观察发电曲线。
```

---

## 12. confidence 生成规则

confidence 表示系统回答可信度，不是模型准确率。

建议范围：

```text
0.75 - 0.90：检索结果充分，厂家和故障类型匹配
0.50 - 0.75：检索结果较相关，但资料不足或范围较宽
0.20 - 0.50：未找到明确资料，仅给出通用建议
0.00 - 0.20：输入过短或无法判断
```

禁止：

```text
1. 返回 1.0
2. 将 confidence 展示为准确率
3. 无检索结果时返回高 confidence
```

---

## 13. trace_id 规则

每次问答和诊断都必须生成唯一 trace_id。

### 13.1 qa trace_id

格式建议：

```text
qa_YYYYMMDD_HHMMSS_random
```

示例：

```text
qa_20260527_143501_a8f2
```

### 13.2 diagnosis trace_id

格式建议：

```text
diag_YYYYMMDD_HHMMSS_random
```

示例：

```text
diag_20260527_143522_b91c
```

---

### 13.3 trace_id 用途

用于：

```text
1. 前端展示追溯编号
2. qa_records 查询
3. diagnosis_records 查询
4. maintenance_tasks.source_trace_id 关联
5. 日志排查
```

---

## 14. qa_records 保存要求

每次调用：

```http
POST /api/retrieval/query
```

无论是否检索到 references，都应保存 qa_records。

必须保存字段：

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

无结果时：

```text
references = []
retrieved_chunks = []
confidence 较低
```

不得因为无结果而不保存记录。

---

## 15. 故障诊断接口

核心接口：

```http
POST /api/diagnosis/analyze
```

---

### 15.1 请求字段

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
| fault_description | string | 是 | 无 | 故障现象 |
| device_status | string | 否 | null | 当前设备状态 |
| include_references | boolean | 否 | true | 是否检索来源 |

---

### 15.2 请求校验

必须校验：

```text
1. fault_description 不为空
2. manufacturer 如填写，必须为 huawei 或 sungrow
3. device_type 第一版必须为 pv_inverter
4. fault_type 如填写，必须在枚举范围内
```

---

## 16. 故障诊断处理流程

```text
1. 接收故障输入
2. 标准化 fault_description
3. 识别或校验 fault_type
4. 根据 fault_type 匹配诊断规则
5. 如果 include_references = true，检索相关 knowledge_chunks
6. 生成 possible_causes
7. 生成 inspection_steps
8. 生成 safety_notes
9. 生成 recommended_actions
10. 生成 confidence
11. 生成 trace_id
12. 保存 diagnosis_records
13. 返回诊断结果
```

---

## 17. 故障诊断规则库

第一版可内置规则库，后续逐步从知识库和大模型增强。

### 17.1 绝缘阻抗低

匹配条件：

```text
fault_type = low_insulation_resistance
或描述中包含：绝缘阻抗低、绝缘低、接地异常、对地绝缘
```

possible_causes：

```text
1. 直流侧组串或电缆绝缘下降
2. 接插件受潮、破损或接触异常
3. 组件受潮、破损或对地漏电
4. 接地连接异常
5. 环境湿度较高导致绝缘水平下降
```

inspection_steps：

```text
1. 确认现场安全条件并按规程执行停机或隔离措施。
2. 查看告警代码、发生时间和关联组串。
3. 检查直流侧电缆、接插件、汇流路径和接地状态。
4. 检查组件是否破损、受潮或存在明显污染。
5. 使用合规仪表检测绝缘阻抗。
6. 处理异常点后恢复运行并复检。
```

safety_notes：

```text
1. 直流侧可能存在高压风险，必须由具备资质人员操作。
2. 绝缘测试应按照厂家手册和电站安全规程执行。
3. 未确认安全前不得随意插拔直流连接器。
```

---

### 17.2 过温 / 风扇异常

匹配条件：

```text
fault_type = over_temperature 或 fan_fault
或描述包含：过温、温度高、降额、风扇、散热
```

possible_causes：

```text
1. 逆变器散热风道堵塞
2. 风扇故障或转速异常
3. 环境温度过高或安装通风不良
4. 长时间高负载运行导致降额
5. 设备内部温度传感异常
```

inspection_steps：

```text
1. 查看告警时间、温度曲线和功率降额情况。
2. 检查进风口、出风口和散热通道。
3. 检查风扇运行状态和异常噪声。
4. 清理灰尘、杂物和遮挡物。
5. 核对安装环境是否满足通风要求。
6. 处理后观察温度和输出功率是否恢复。
```

safety_notes：

```text
1. 高温状态下避免直接接触散热部件。
2. 涉及开盖检查时必须遵守电气安全规程。
3. 风扇更换应使用符合厂家要求的部件。
```

---

### 17.3 通信中断 / 设备离线

匹配条件：

```text
fault_type = communication_interruption 或 device_offline
或描述包含：通信中断、设备离线、平台离线、数据不上报
```

possible_causes：

```text
1. 监控平台或采集器通信异常
2. RS485、网线或通信模块连接异常
3. 设备本体停机或掉电
4. 网络配置、IP、网关或平台接入异常
5. 数据上报链路中断
```

inspection_steps：

```text
1. 判断设备是否真实停机，还是仅监控平台离线。
2. 查看 FusionSolar 或监控平台离线时间。
3. 检查采集器供电、网络和指示灯状态。
4. 检查 RS485、网线、通信模块连接。
5. 核对通信参数、IP、网关和平台接入配置。
6. 恢复通信后确认数据是否正常上报。
```

safety_notes：

```text
1. 通信排查不等于设备无电气风险，进入现场仍需遵守安全规程。
2. 不应随意修改通信参数，避免影响批量设备接入。
```

---

### 17.4 MPPT 异常 / 功率偏低

匹配条件：

```text
fault_type = mppt_abnormal 或 low_power_generation
或描述包含：MPPT、功率偏低、发电量低、发电异常
```

possible_causes：

```text
1. 组串电压或电流不一致
2. 组件遮挡、污染或老化
3. 直流输入接线异常
4. 逆变器发生过温降额或限功率运行
5. MPPT 跟踪异常
6. 电网侧限制导致输出功率受限
```

inspection_steps：

```text
1. 对比同区域同型号逆变器的功率曲线。
2. 查看各 MPPT 支路电压、电流是否明显偏离。
3. 检查组串遮挡、组件污染、接线松动。
4. 查看是否存在过温、限功率或并网异常告警。
5. 清理或处理异常组串后观察发电量变化。
6. 记录处理前后的功率和发电量数据。
```

safety_notes：

```text
1. 直流侧检测必须遵守安全操作规程。
2. 不得在未隔离风险的情况下直接拆接组串。
```

---

### 17.5 并网异常 / 交流过压欠压

匹配条件：

```text
fault_type = grid_connection_fault / ac_overvoltage / ac_undervoltage
或描述包含：并网失败、电网过压、电网欠压、频率异常
```

possible_causes：

```text
1. 并网点电压超出逆变器允许范围
2. 电网频率异常
3. 交流侧接线或开关状态异常
4. 保护参数或并网参数配置不匹配
5. 场站侧电气设备异常
```

inspection_steps：

```text
1. 查看逆变器并网告警和发生时间。
2. 测量并网点电压和频率。
3. 检查交流侧开关、接线和保护装置状态。
4. 核对并网参数设置是否符合当地要求。
5. 如电网侧异常，应联系电站电气负责人或电网侧处理。
```

safety_notes：

```text
1. 交流侧检测存在触电风险，必须由具备资质人员执行。
2. 不得擅自修改并网保护参数。
```

---

## 18. diagnosis_records 保存要求

每次调用：

```http
POST /api/diagnosis/analyze
```

必须保存 diagnosis_records。

字段：

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

---

## 19. 故障诊断 references 规则

如果 `include_references = true`，诊断模块可调用同一检索器，从 knowledge_chunks 中检索相关资料。

检索 query 可由以下信息组合：

```text
manufacturer
product_series
fault_type 中文名称
alarm_code
fault_description
```

例如：

```text
阳光 SG 系列 逆变器过温 风扇 散热 降额
```

如果检索到资料：

```text
references 不为空
```

如果没有资料：

```text
references = []
```

不得编造。

---

## 20. recommended_actions 生成规则

推荐处理措施应比 inspection_steps 更偏向处理建议。

例如过温：

inspection_steps：

```text
检查风道、检查风扇、查看温度曲线
```

recommended_actions：

```text
清理散热通道
更换异常风扇
改善通风条件
联系厂家技术支持
```

---

## 21. 安全注意事项要求

光伏逆变器涉及高压直流和交流并网风险，因此 safety_notes 必须在诊断结果中单独输出。

每个诊断结果至少包含 1 条安全提示。

通用安全提示：

```text
1. 检修前必须遵守厂家手册和电站安全操作规程。
2. 涉及直流侧、交流侧、开盖检查、绝缘测试等操作时，必须由具备资质人员执行。
3. 未确认设备安全状态前，不得随意插拔电缆、接插件或通信模块。
```

---

## 22. 前端展示要求

### 22.1 检索问答页面

必须展示：

```text
answer
suggested_steps
references
retrieved_chunks
confidence
trace_id
```

references 为空时显示：

```text
当前知识库未检索到足够相关资料，请补充华为或阳光电源逆变器手册、告警代码或检修规程。
```

---

### 22.2 故障诊断页面

必须展示：

```text
possible_causes
inspection_steps
safety_notes
recommended_actions
references
confidence
trace_id
```

安全提示必须醒目展示。

---

### 22.3 记录追溯页面

必须能查询：

```text
qa_records
diagnosis_records
```

并展示：

```text
trace_id
references
retrieved_chunks
created_at
```

---

## 23. 第一版验收标准

### 23.1 检索问答验收

准备华为样例文档：

```text
sample_huawei_sun2000_low_insulation.txt
```

上传并解析后，调用：

```http
POST /api/retrieval/query
```

问题：

```text
华为 SUN2000 逆变器报绝缘阻抗低，应该怎么排查？
```

必须满足：

```text
1. answer 不为空
2. suggested_steps 不为空
3. references 不为空
4. retrieved_chunks 不为空
5. references 来自真实 knowledge_chunks
6. confidence 合理，不为 1.0
7. trace_id 存在
8. qa_records 写入成功
```

---

### 23.2 阳光电源问答验收

准备阳光样例文档：

```text
sample_sungrow_sg_overtemperature.txt
```

问题：

```text
阳光 SG 系列逆变器过温降额怎么处理？
```

必须满足：

```text
1. 检索到 sungrow / SG 相关 chunks
2. references 中 manufacturer = sungrow
3. answer 中包含过温、风扇、散热或降额相关内容
4. qa_records 写入成功
```

---

### 23.3 无资料场景验收

当知识库为空或问题明显无关时：

```text
references = []
retrieved_chunks = []
confidence 较低
answer 明确提示需要补充资料
qa_records 仍写入
```

不得编造来源。

---

### 23.4 故障诊断验收

输入：

```json
{
  "manufacturer": "sungrow",
  "product_series": "SG",
  "device_type": "pv_inverter",
  "fault_type": "over_temperature",
  "fault_description": "阳光 SG 系列逆变器中午高温时频繁出现过温降额，发电功率下降。"
}
```

必须满足：

```text
1. possible_causes 不为空
2. inspection_steps 不为空
3. safety_notes 不为空
4. recommended_actions 不为空
5. diagnosis_records 写入成功
6. trace_id 存在
```

---

## 24. 后续增强路线

第一版完成真实闭环后，再考虑增强。

### 24.1 pgvector 阶段

引入：

```text
PostgreSQL pgvector
embedding 字段
embedding_model
hybrid search
```

检索方式升级为：

```text
关键词检索 + 向量检索 + 规则 rerank
```

---

### 24.2 大模型生成阶段

引入 LLM 后，必须保持：

```text
1. references 仍来自真实 chunks
2. prompt 中只能使用检索到的上下文
3. 无资料时模型不能编造手册内容
4. 回答仍保存 qa_records
5. 模型调用保存 model_call_logs
```

---

### 24.3 reranker 阶段

可引入轻量 reranker，对 top_k 扩展为：

```text
先召回 top_30
再 rerank top_5
```

但必须考虑 LoongArch 部署兼容性。

---

### 24.4 OCR 阶段

OCR 只负责把扫描件转文本，不改变 references 规则。

OCR 输出仍需：

```text
写入 knowledge_documents
写入 knowledge_chunks
参与检索
```

---

## 25. 禁止事项

检索问答和故障诊断开发中禁止：

```text
1. 检索不到内容时编造 references
2. 不写 qa_records
3. 不写 diagnosis_records
4. 把 confidence 写成 1.0
5. 将系统做成普通聊天机器人
6. 回答中承诺“确定故障原因”
7. 忽略安全提示
8. 只用前端假数据展示问答结果
9. 未真实连接 PostgreSQL 就宣称问答闭环完成
10. 将范围扩展到泛新能源设备或其他厂家
```

---

## 26. 与其他文档关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
03_database_schema_design.md
04_api_contract_design.md
05_frontend_page_and_interaction_spec.md
06_knowledge_base_and_document_processing_spec.md
```

其中：

- `01` 定义产品范围；
- `02` 定义技术架构；
- `03` 定义数据库结构；
- `04` 定义 API 契约；
- `05` 定义前端页面；
- `06` 定义知识库处理；
- `07` 定义检索问答和故障诊断逻辑。

---

## 27. 下一步建议

本文档确认后，下一份建议编写：

```text
08_deployment_and_loongarch_kylin_spec.md
```

下一份应重点定义：

```text
LoongArch + Kylin 原生部署
Python venv
PostgreSQL 原生服务
systemd
Nginx
前端 build
后端日志
上传目录
备份策略
不使用 Docker 的正式路线
```

---

## 28. Task 13 模型增强接入规则

Task 13 将 Model Gateway 作为可选增强层接入检索问答、故障诊断和 SOP 生成。增强层不得替换第一版本 rule-based 主线。

### 28.1 启用方式

业务请求可携带以下可选字段：

```json
{
  "enable_model_enhancement": false,
  "model_provider": "rule_based",
  "allow_model_fallback": true
}
```

默认不启用模型增强，保持原有检索、诊断、SOP 生成行为。

### 28.2 处理顺序

启用模型增强时，必须按以下顺序执行：

```text
1. 执行现有 rule-based 检索、诊断或 SOP 生成
2. 保留真实 references / retrieved_chunks / related_history
3. 将规则结果和真实来源摘要交给 Model Gateway
4. 仅增强文字表达或补充说明
5. 模型失败时回退原始规则结果
```

### 28.3 来源约束

模型增强不得：

```text
1. 新增不存在的文档标题、章节、页码、chunk 或维修记录
2. 删除真实 references
3. 改写 retrieved_chunks、related_history 或 SOP checklist 结构
4. 弱化电气安全要求
5. 声称已经确定唯一故障原因
```

无检索结果时，`references` 和 `retrieved_chunks` 继续返回空列表，模型只能说明当前知识库依据不足。

### 28.4 记录要求

每次实际模型调用由 Model Gateway 写入已有 `model_call_logs`。业务响应需要返回：

```text
model_enhanced
fallback_used
model_provider
model_name
model_call_trace_id
```

`qa_records` 和 `diagnosis_records` 应尽量保存实际 `model_provider`、`model_name`、`confidence`、`references` 与相关追溯字段。

---

## Task 14B Cloud Model Enhancement Guardrails

When `cloud_openai` is enabled, model enhancement is still a wording and explanation layer only.

For retrieval QA, diagnosis, and SOP generation:

- The rule-based result must be generated first.
- Real `references`, `retrieved_chunks`, `related_history`, SOP steps, and SOP checklists must be preserved.
- The model must not invent document titles, sections, page numbers, chunk IDs, sources, alarm codes, or history records.
- Electrical safety notes must not be weakened.
- If the cloud provider is disabled or not configured and fallback is allowed, the response should use `rule_based` fallback and mark `fallback_used=true`.
- If fallback is not allowed, the model call should fail with a structured error instead of fabricating output.
