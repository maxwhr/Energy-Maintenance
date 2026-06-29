# 06 知识库与文档处理规格文档

**Document Name:** `06_knowledge_base_and_document_processing_spec.md`  
**Project:** Energy-Maintenance  
**Version:** v1.0  
**Status:** Baseline Draft  
**Core Scenario:** Huawei / Sungrow PV Inverter Maintenance Knowledge Base  
**Backend Stack:** FastAPI + SQLAlchemy + Alembic + PostgreSQL  
**Document Processing:** txt / md / pdf / docx  

---

## 1. 文档目的

本文档用于定义 Energy-Maintenance 第一版知识库模块的文档上传、存储、解析、清洗、切片、入库、状态流转、异常处理和验收标准。

本项目第一版已明确聚焦：

> 华为与阳光电源光伏逆变器检修知识检索与作业辅助。

因此，知识库不再泛化为“所有新能源设备资料库”，而是重点管理以下资料：

```text
华为 SUN2000 / FusionSolar 相关资料
阳光电源 Sungrow SG 系列相关资料
光伏逆变器用户手册
光伏逆变器安装与调试资料
告警代码说明
故障排查流程
检修作业规程
巡检规范
模拟检修工单
```

本文档的目标是让 Codex 后续开发时能够直接照此实现，并避免出现：

```text
1. 只保存文件名，不解析真实内容
2. 只生成模拟 chunks，不写入 PostgreSQL
3. 文档解析失败但状态仍显示成功
4. references 找不到真实来源
5. 页面能上传但后端没有形成检索数据
6. 知识库资料范围继续扩散到泛新能源设备
```

---

## 2. 知识库模块定位

知识库模块是 Energy-Maintenance 的基础模块。

其核心作用不是“文件网盘”，而是将华为和阳光电源光伏逆变器资料转换为可检索、可追溯、可用于问答和诊断的结构化知识片段。

核心流程如下：

```text
用户上传文档
    ↓
保存原始文件
    ↓
记录 knowledge_documents
    ↓
解析文本
    ↓
清洗文本
    ↓
按规则切片
    ↓
生成 knowledge_chunks
    ↓
更新 parse_status 和 chunk_count
    ↓
供检索问答和故障诊断调用
```

---

## 3. 第一版知识库资料范围

### 3.1 支持厂家

第一版仅支持：

| manufacturer | 中文名称 | 说明 |
|---|---|---|
| huawei | 华为 | SUN2000 / FusionSolar 体系 |
| sungrow | 阳光电源 | SG 系列逆变器 |

不得在第一版主动扩展到锦浪、固德威、古瑞瓦特、上能、电气等厂家。

---

### 3.2 支持设备

第一版只支持：

| device_type | 中文名称 |
|---|---|
| pv_inverter | 光伏逆变器 |

不主动支持：

```text
储能电池系统
箱式变压器
电力巡检设备
泛新能源设备
车辆维修设备
```

---

### 3.3 支持产品系列

| manufacturer | product_series | 说明 |
|---|---|---|
| huawei | SUN2000 | 华为光伏逆变器主力系列 |
| huawei | FusionSolar | 华为智能光伏运维体系，可用于告警/平台资料 |
| sungrow | SG | 阳光电源 SG 系列逆变器 |

---

### 3.4 支持文档类型

| document_type | 中文名称 | 说明 |
|---|---|---|
| manual | 设备手册 | 用户手册、安装手册、维护手册 |
| alarm_code | 告警代码 | 告警码、错误码、事件说明 |
| sop | 检修规程 | 标准化作业流程 |
| fault_case | 故障案例 | 历史或模拟故障处理案例 |
| inspection_standard | 巡检规范 | 日常巡检与周期性检查 |
| maintenance_record | 检修记录 | 已处理工单、复检记录 |

---

## 4. 支持文件类型

第一版支持：

```text
.txt
.md
.pdf
.docx
```

### 4.1 txt

必须真实支持。

处理要求：

```text
1. 优先使用 UTF-8 解码
2. UTF-8 失败时尝试 GBK
3. 解析后必须得到非空文本
4. 保留换行、标题、编号、故障码、设备型号
```

### 4.2 md

必须真实支持。

处理要求：

```text
1. 按文本方式解析
2. 保留 Markdown 标题层级
3. 保留列表、表格文本和代码块中的告警码
4. 不要求渲染 Markdown，只提取文本
```

### 4.3 pdf

第一版支持文本型 PDF。

推荐使用：

```text
pypdf
```

原因：

```text
1. 相对轻量
2. 纯 Python 依赖更友好
3. 对 LoongArch + Kylin 兼容性风险相对低
```

第一版不做：

```text
扫描版 PDF OCR
复杂版式恢复
图片表格识别
```

处理要求：

```text
1. 按页提取文本
2. 记录 page_count
3. 尽量保留页码信息
4. 单页解析失败不能导致整个服务崩溃
5. 如果整体提取文本为空，应 parse_status = failed
```

### 4.4 docx

第一版支持 docx。

推荐使用：

```text
python-docx
```

处理要求：

```text
1. 提取段落文本
2. 提取表格文本
3. 保留告警码、参数、型号、单位
4. 空文档应返回明确错误
```

### 4.5 不支持文件类型

以下文件不支持：

```text
.exe
.zip
.rar
.7z
.png
.jpg
.jpeg
.xlsx
.pptx
.html
```

说明：

- 图片和扫描件 OCR 属于后续阶段；
- Excel、PPT 资料如需支持，应后续单独设计；
- 压缩包上传暂不做。

不支持类型必须返回明确错误：

```json
{
  "code": 415,
  "message": "Unsupported document extension: exe",
  "data": null
}
```

---

## 5. 上传配置

### 5.1 环境变量

`backend/.env` 应包含：

```env
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_DOCUMENT_EXTENSIONS=txt,md,pdf,docx
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=150
```

### 5.2 上传目录要求

默认上传目录：

```text
backend/storage/uploads
```

要求：

```text
1. UPLOAD_DIR 必须解析为绝对路径
2. 上传目录不得位于 frontend 目录下
3. 上传目录不存在时应自动创建
4. 上传路径不得允许路径穿越
5. 文件保存路径应写入 knowledge_documents.file_path
```

推荐目录结构：

```text
backend/storage/uploads/
├── 2026/
│   ├── 05/
│   │   ├── huawei/
│   │   │   └── document-id/
│   │   │       └── original_file.pdf
│   │   └── sungrow/
│   │       └── document-id/
│   │           └── original_file.docx
```

如实现成本较高，第一版可简化为：

```text
backend/storage/uploads/{document_id}/{safe_file_name}
```

但必须保证不覆盖同名文件。

### 5.3 文件大小限制

默认最大：

```text
50MB
```

超过限制返回：

```json
{
  "code": 413,
  "message": "Uploaded file exceeds 50MB limit",
  "data": null
}
```

### 5.4 文件名安全处理

上传文件名必须进行安全处理。

要求：

```text
1. 去除路径分隔符
2. 去除 .. 等路径穿越片段
3. 保留扩展名
4. 必要时增加 uuid 前缀或 document_id 目录
5. 不信任用户上传的原始文件名
```

---

## 6. 文档上传接口行为

核心接口：

```http
POST /api/knowledge/documents/upload
```

请求类型：

```text
multipart/form-data
```

字段：

```text
file
title
manufacturer
product_series
model
device_type
document_type
source
summary
```

其中必须字段：

```text
file
manufacturer
device_type
document_type
```

第一版建议强制校验：

```text
manufacturer in [huawei, sungrow]
device_type = pv_inverter
document_type in [manual, alarm_code, sop, fault_case, inspection_standard, maintenance_record]
```

---

## 7. 文档处理状态流转

### 7.1 parse_status 状态

| 状态 | 含义 |
|---|---|
| pending | 文档已创建，等待解析 |
| processing | 正在解析 |
| parsed | 解析成功 |
| failed | 解析失败 |

### 7.2 正常状态流转

```text
pending
  ↓
processing
  ↓
parsed
```

### 7.3 异常状态流转

```text
pending
  ↓
processing
  ↓
failed
```

失败时必须写入：

```text
error_message
```

并保证：

```text
chunk_count = 0
```

### 7.4 状态一致性要求

上传成功后：

```text
parse_status = parsed
chunk_count > 0
knowledge_chunks 中存在对应 document_id 的切片
```

上传失败后：

```text
parse_status = failed
error_message 非空
chunk_count = 0
```

不得出现：

```text
parse_status = parsed 但 chunk_count = 0
parse_status = failed 但 error_message 为空
chunk_count 与实际 chunks 数量不一致
```

---

## 8. 文档处理模块结构

建议目录：

```text
backend/app/knowledge/
├── __init__.py
├── file_storage.py
├── document_parser.py
├── text_cleaner.py
├── text_splitter.py
└── document_processor.py
```

### 8.1 file_storage.py

职责：

```text
1. 校验扩展名
2. 校验文件大小
3. 生成安全文件名
4. 保存原始文件
5. 返回文件元数据
```

返回结构建议：

```python
{
    "file_name": "sample_huawei_sun2000_alarm.txt",
    "file_path": "storage/uploads/doc-id/sample_huawei_sun2000_alarm.txt",
    "file_ext": "txt",
    "file_size": 12560
}
```

不得处理：

```text
文档解析
文本清洗
数据库写入
```

### 8.2 document_parser.py

职责：

```text
1. 根据 file_ext 选择解析器
2. 提取文本
3. 返回 ParsedDocument
4. 记录 warnings
```

统一返回结构：

```python
ParsedDocument(
    text: str,
    page_count: int | None,
    metadata: dict,
    warnings: list[str]
)
```

解析器建议：

| ext | parser |
|---|---|
| txt | TextParser |
| md | MarkdownTextParser |
| pdf | PdfTextParser |
| docx | DocxTextParser |

### 8.3 text_cleaner.py

职责：

```text
1. 统一换行
2. 合并过多空行
3. 去除不可见字符
4. 保留技术关键内容
5. 不过度清洗
```

必须保留：

```text
SUN2000
FusionSolar
SG110CX
SG320HX
MPPT
PID
AFCI
RS485
Modbus
绝缘阻抗
过温
并网
电压
电流
告警码
故障码
单位
编号
```

禁止清洗掉：

```text
数字
英文缩写
设备型号
告警代码
参数单位
章节编号
```

### 8.4 text_splitter.py

职责：

```text
1. 按长度切片
2. 支持 overlap
3. 尽量按段落边界切分
4. 为每个 chunk 生成元数据
```

默认配置：

```text
chunk_size = 1000
chunk_overlap = 150
```

允许范围：

```text
500 <= chunk_size <= 2000
50 <= chunk_overlap <= 300
```

每个 chunk 应包含：

```text
chunk_index
content
section_title
char_count
page_number
metadata_json
```

### 8.5 document_processor.py

职责：

```text
组织完整处理流程
```

流程：

```text
1. 接收上传文件和业务元数据
2. 调用 file_storage 保存文件
3. 创建或更新 knowledge_documents
4. 设置 parse_status = processing
5. 调用 document_parser 提取文本
6. 调用 text_cleaner 清洗文本
7. 调用 text_splitter 生成 chunks
8. 写入 knowledge_chunks
9. 更新 parse_status = parsed
10. 更新 chunk_count
11. 失败时写入 parse_status = failed 和 error_message
```

必须尽量使用数据库事务保证一致性。

---

## 9. ParsedDocument 规格

建议结构：

```python
class ParsedDocument:
    text: str
    page_count: int | None
    metadata: dict
    warnings: list[str]
```

示例：

```json
{
  "text": "华为 SUN2000 逆变器告警排查...",
  "page_count": 12,
  "metadata": {
    "parser": "pypdf",
    "file_ext": "pdf",
    "language": "zh-CN"
  },
  "warnings": []
}
```

解析失败时应抛出业务异常或返回失败结果，不得静默返回空文本后继续切片。

---

## 10. TextChunk 规格

建议结构：

```python
class TextChunk:
    chunk_index: int
    content: str
    section_title: str | None
    char_count: int
    page_number: int | None
    metadata_json: dict
```

示例：

```json
{
  "chunk_index": 0,
  "content": "当华为 SUN2000 逆变器出现绝缘阻抗低告警时，应首先检查直流侧组串、电缆绝缘和接地情况...",
  "section_title": "绝缘阻抗低告警处理",
  "char_count": 356,
  "page_number": 12,
  "metadata_json": {
    "splitter": "paragraph_overlap",
    "chunk_size": 1000,
    "overlap": 150
  }
}
```

---

## 11. 文本清洗规则

### 11.1 基础清洗

应执行：

```text
1. 将 \r\n 和 \r 统一为 \n
2. 去除首尾空白
3. 将连续 3 个以上空行压缩为 2 个
4. 将连续空格适度压缩
5. 删除不可见控制字符
```

### 11.2 技术内容保护

不得删除：

```text
设备型号：SUN2000-100KTL、SG320HX
告警码：Alarm ID、Error Code、TEMP_HIGH
通信协议：RS485、Modbus
参数：1000V、50Hz、35A、85℃
单位：V、A、kW、℃、MΩ
编号：1.1、2.3.4
表格中的关键字段
```

### 11.3 中英文混合资料处理

华为和阳光电源资料可能存在中英文混合。

清洗时必须保留：

```text
中文故障描述
英文设备型号
英文缩写
英文告警词
数字参数
```

---

## 12. 切片策略

### 12.1 第一版默认切片策略

采用：

```text
段落优先 + 字符长度限制 + overlap
```

基本规则：

```text
1. 先按段落切分
2. 累积段落直到接近 chunk_size
3. 超过 chunk_size 时生成一个 chunk
4. 下一个 chunk 保留 overlap 字符上下文
5. 空段落忽略
```

### 12.2 为什么不按句子切分

逆变器手册中经常包含：

```text
编号步骤
表格
告警码
注意事项
参数列表
```

按句子切分可能破坏上下文，因此第一版优先按段落和长度切分。

### 12.3 chunk_size 建议

默认：

```text
1000 characters
```

原因：

```text
1. 足够容纳一段故障说明和处理建议
2. 不会过长导致检索结果臃肿
3. 适合后续 RAG prompt 拼接
```

### 12.4 overlap 建议

默认：

```text
150 characters
```

原因：

```text
1. 避免上下文断裂
2. 保留步骤之间衔接
3. 对检索和问答更稳定
```

### 12.5 section_title 提取

应尽量从文本中识别章节标题。

简单规则：

```text
1. Markdown 标题：#、##、###
2. 以数字编号开头：1.、1.1、2.3.4
3. 包含“告警”“故障”“处理”“维护”“检查”“安全”等短标题
4. PDF/DOCX 中独立短行可作为候选标题
```

无法识别时：

```text
section_title = null
```

不要编造标题。

---

## 13. 数据库入库要求

### 13.1 knowledge_documents 写入字段

上传处理后必须写入或更新：

```text
title
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

### 13.2 knowledge_chunks 写入字段

每个切片必须写入：

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

其中：

```text
embedding_status = pending
status = active
```

### 13.3 冗余字段同步

`knowledge_chunks` 中以下字段必须从 `knowledge_documents` 同步：

```text
manufacturer
product_series
device_type
document_type
```

原因：

```text
1. 检索过滤更方便
2. references 构建更直接
3. 后续 pgvector 检索可减少 join 复杂度
```

### 13.4 一致性校验

入库后应保证：

```text
knowledge_documents.chunk_count = 实际 knowledge_chunks 数量
knowledge_documents.parse_status = parsed
knowledge_chunks.document_id 正确
knowledge_chunks.content 非空
```

---

## 14. 异常处理规则

### 14.1 空文件

返回：

```json
{
  "code": 400,
  "message": "Uploaded file is empty",
  "data": null
}
```

### 14.2 不支持扩展名

返回：

```json
{
  "code": 415,
  "message": "Unsupported document extension: xlsx",
  "data": null
}
```

### 14.3 文件过大

返回：

```json
{
  "code": 413,
  "message": "Uploaded file exceeds 50MB limit",
  "data": null
}
```

### 14.4 文本提取为空

返回：

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

### 14.5 数据库写入失败

返回：

```json
{
  "code": 503,
  "message": "Database service unavailable or write failed",
  "data": null
}
```

不得把数据库失败显示为上传成功。

---

## 15. 前端交互要求

知识库页面应实现：

```text
1. 文件选择
2. 厂家选择
3. 产品系列选择
4. 文档类型选择
5. 上传并解析
6. 展示解析状态
7. 展示切片数量
8. 查看切片内容
9. 显示失败原因
```

上传时 loading 文案：

```text
正在上传并解析文档，请稍候...
```

解析成功：

```text
文档解析完成，共生成 N 个知识切片。
```

解析失败：

```text
文档解析失败：{error_message}
```

---

## 16. 样例资料准备规范

为了保证第一版验收稳定，必须准备最小样例资料，不完全依赖大型 PDF 手册。

推荐准备以下本地样例 txt 或 md：

```text
backend/storage/samples/sample_huawei_sun2000_low_insulation.txt
backend/storage/samples/sample_huawei_fusionsolar_communication.txt
backend/storage/samples/sample_sungrow_sg_overtemperature.txt
backend/storage/samples/sample_sungrow_sg_mppt_low_power.txt
```

### 16.1 华为样例 1：绝缘阻抗低

文件名：

```text
sample_huawei_sun2000_low_insulation.txt
```

元数据：

```text
manufacturer = huawei
product_series = SUN2000
device_type = pv_inverter
document_type = alarm_code
```

内容应包含：

```text
SUN2000
绝缘阻抗低
直流侧组串
电缆绝缘
接地异常
组件受潮
排查步骤
安全注意事项
```

### 16.2 华为样例 2：通信中断

文件名：

```text
sample_huawei_fusionsolar_communication.txt
```

元数据：

```text
manufacturer = huawei
product_series = FusionSolar
device_type = pv_inverter
document_type = sop
```

内容应包含：

```text
FusionSolar
设备离线
通信中断
采集器
网络连接
RS485
数据上报
排查流程
```

### 16.3 阳光样例 1：过温降额

文件名：

```text
sample_sungrow_sg_overtemperature.txt
```

元数据：

```text
manufacturer = sungrow
product_series = SG
device_type = pv_inverter
document_type = sop
```

内容应包含：

```text
SG 系列
逆变器过温
降额运行
风扇异常
散热风道
环境温度
清理维护
```

### 16.4 阳光样例 2：MPPT 异常和功率偏低

文件名：

```text
sample_sungrow_sg_mppt_low_power.txt
```

元数据：

```text
manufacturer = sungrow
product_series = SG
device_type = pv_inverter
document_type = fault_case
```

内容应包含：

```text
MPPT 异常
功率偏低
组串不一致
遮挡
组件污染
直流输入异常
发电量异常
```

---

## 17. 真实资料准备建议

第一版可以使用公开资料和人工整理资料组合。

### 17.1 公开资料

可准备：

```text
华为 SUN2000 用户手册
华为 FusionSolar 告警和运维说明
阳光 SG 系列用户手册
阳光逆变器维护说明
```

注意：

```text
1. 公开资料应保留来源字段 source
2. 不要上传涉及版权或内部保密的资料到公开仓库
3. 比赛演示可使用节选或自整理摘要
```

### 17.2 人工整理资料

建议人工整理更适合检索问答的专题文档：

```text
华为 SUN2000 绝缘阻抗低排查流程
华为 FusionSolar 设备离线排查流程
阳光 SG 系列过温降额处理流程
阳光 SG 系列 MPPT 异常与功率偏低案例
```

人工整理文档更利于演示，因为内容聚焦、切片质量高、检索命中稳定。

---

## 18. 解析质量评估标准

上传文档后，不能只看是否生成 chunk，还要看切片质量。

### 18.1 文本质量

应满足：

```text
1. 内容不是乱码
2. 设备型号、告警码、参数保留
3. 段落顺序合理
4. 不出现大量空白
5. 不出现大量无意义页眉页脚
```

### 18.2 切片质量

应满足：

```text
1. 单个 chunk 不应过短
2. 单个 chunk 不应过长
3. 一个故障处理流程尽量不要被严重切断
4. section_title 尽量准确
5. chunk_index 连续
```

### 18.3 检索质量

上传后应能通过以下问题检索到相关切片：

```text
华为 SUN2000 绝缘阻抗低怎么排查？
FusionSolar 显示设备离线怎么办？
阳光 SG 系列逆变器过温降额怎么处理？
SG 系列 MPPT 异常导致功率偏低如何检查？
```

---

## 19. 知识库接口验收

### 19.1 上传验收

命令示例：

```bash
curl -X POST http://127.0.0.1:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_huawei_sun2000_low_insulation.txt" \
  -F "manufacturer=huawei" \
  -F "product_series=SUN2000" \
  -F "device_type=pv_inverter" \
  -F "document_type=alarm_code" \
  -F "source=local_sample"
```

必须返回：

```text
parse_status = parsed
chunk_count > 0
```

### 19.2 切片查询验收

```bash
curl http://127.0.0.1:8000/api/knowledge/documents/{document_id}/chunks
```

必须满足：

```text
items 不为空
content 包含上传文件中的真实内容
manufacturer = huawei
product_series = SUN2000
device_type = pv_inverter
```

### 19.3 数据库一致性验收

执行 SQL：

```sql
SELECT chunk_count FROM knowledge_documents WHERE id = :document_id;

SELECT COUNT(*) FROM knowledge_chunks WHERE document_id = :document_id;
```

两者必须一致。

---

## 20. 与检索问答的衔接要求

知识库模块必须为 `/api/retrieval/query` 提供可靠数据。

检索时只应使用：

```text
knowledge_documents.parse_status = parsed
knowledge_documents.status = active
knowledge_chunks.status = active
```

检索结果构建 references 时必须包含：

```text
document_id
document_title
manufacturer
product_series
document_type
device_type
section_title
chunk_index
page_number
source
score
```

如果知识库未上传任何资料，检索问答应返回：

```text
references = []
retrieved_chunks = []
```

不得编造来源。

---

## 21. 与故障诊断的衔接要求

故障诊断第一版可使用规则型逻辑，但后续应逐步结合知识库检索。

当 `include_references = true` 时，诊断服务可尝试从 knowledge_chunks 中检索相关内容。

例如：

```text
fault_type = over_temperature
manufacturer = sungrow
product_series = SG
```

应优先检索：

```text
阳光 SG 系列过温
风扇异常
散热风道
降额运行
```

如果检索不到资料，references 为空，不得编造。

---

## 22. LoongArch + Kylin 兼容性要求

知识库处理依赖应尽量选择对国产环境友好的库。

### 22.1 推荐依赖

```text
pypdf
python-docx
python-multipart
```

### 22.2 暂不优先选择

```text
PyMuPDF
大型 OCR 本地依赖
复杂 C++ 编译依赖
仅支持 x86 的模型库
```

原因：

```text
1. LoongArch 编译适配风险较高
2. 本项目第一版不需要扫描 OCR
3. 优先保证文档处理链路可部署
```

---

## 23. 后续增强规划

第一版完成后，可逐步增强：

```text
1. OCR 扫描件识别
2. Excel 告警表解析
3. PDF 表格结构化抽取
4. pgvector embedding
5. 文档版本管理
6. 文档审核发布
7. 知识片段人工修订
8. 资料来源可信度评分
```

但这些不属于第一版必须完成内容。

---

## 24. 禁止事项

知识库模块开发中禁止：

```text
1. 只保存文档元数据，不解析内容
2. 用内存模拟 knowledge_chunks
3. parse_status = parsed 但没有 chunks
4. 上传失败却返回 success
5. 解析失败不保存 error_message
6. 删除数字、告警码、设备型号、参数单位
7. 将上传文件保存到 frontend 目录
8. 支持泛新能源设备而不聚焦光伏逆变器
9. 将扫描版 PDF OCR 作为第一版硬性要求
10. 未真实连接 PostgreSQL 就宣称入库完成
```

---

## 25. 与其他文档关系

本文档依赖：

```text
01_project_scope_and_product_requirements.md
02_technical_stack_and_architecture.md
03_database_schema_design.md
04_api_contract_design.md
05_frontend_page_and_interaction_spec.md
```

其中：

- `01` 定义产品范围；
- `02` 定义技术栈；
- `03` 定义数据库字段；
- `04` 定义接口契约；
- `05` 定义前端页面；
- `06` 定义知识库处理细节。

---

## 26. 下一步建议

本文档确认后，下一份建议编写：

```text
07_retrieval_qa_and_fault_diagnosis_spec.md
```

下一份文档应重点定义：

```text
关键词检索策略
中文检索规则
manufacturer / product_series 过滤
references 构建规则
规则型回答生成
故障诊断规则
trace_id 追溯
qa_records / diagnosis_records 保存
后续 pgvector 和大模型增强路线
```
