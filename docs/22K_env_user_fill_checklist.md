# Task 22K ENV User Fill Checklist

本文件用于说明真实外部 API 接入前，用户需要在 `backend/.env` 中填写哪些 key。

安全边界：

- 本任务只补齐 `backend/.env` 配置结构。
- 不要把真实 API Key 写入 `backend/.env.example`。
- 不要把真实 API Key 写入文档、截图、提交信息或终端输出。
- 当前 External API Gateway 仍是 `dry-run/mock-run only`。
- 仅填写 `.env` 不会自动真实调用 API。
- 真实外呼需要后续 Task 22K 修改 gateway / adapters，显式打开 real-run。

## 1. 最小可接入方案

最少只需要 1 个 API：

1. MIMO 2.5

需要替换：

```text
MIMO_ENABLED=true
MIMO_BASE_URL=<FILL_MIMO_BASE_URL>
MIMO_API_KEY=<FILL_MIMO_API_KEY>
MIMO_MODEL=mimo-2.5
MIMO_API_PROFILE=openai_compatible_vision
```

用途：

- 多模态证据智能体的故障现场图像理解。
- 告警屏幕、铭牌、现场图片的视觉分析预留入口。
- `media_mimo_analysis` 工具的第一优先级 Provider。

## 2. 推荐企业级方案

推荐填写 3 个 API：

1. MIMO 2.5
2. Cloud Text LLM
3. OCR API

需要替换：

```text
MIMO_BASE_URL=<FILL_MIMO_BASE_URL>
MIMO_API_KEY=<FILL_MIMO_API_KEY>

CLOUD_LLM_BASE_URL=<FILL_CLOUD_LLM_BASE_URL>
CLOUD_LLM_API_KEY=<FILL_CLOUD_LLM_API_KEY>
CLOUD_LLM_MODEL=<FILL_CLOUD_LLM_MODEL>

OCR_API_BASE_URL=<FILL_OCR_API_BASE_URL>
OCR_API_KEY=<FILL_OCR_API_KEY>
OCR_API_MODEL=<FILL_OCR_API_MODEL>
```

用途：

- MIMO 2.5：多模态证据和图像故障线索。
- Cloud Text LLM：模型网关对话、文本摘要、结构化抽取、安全审核增强。
- OCR API：告警屏幕、铭牌、现场图片文字识别。

## 3. 可选增强方案

最多可配置 5 个 API / 服务：

1. MIMO 2.5
2. Cloud Text LLM
3. OCR API
4. Cloud Vision
5. Local llama.cpp

可选替换：

```text
CLOUD_VISION_BASE_URL=<FILL_CLOUD_VISION_BASE_URL>
CLOUD_VISION_API_KEY=<FILL_CLOUD_VISION_API_KEY>
CLOUD_VISION_MODEL=<FILL_CLOUD_VISION_MODEL>

LOCAL_LLM_ENABLED=true
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080
LOCAL_LLM_MODEL=local-gguf-model
LOCAL_LLM_API_KEY=
```

用途：

- Cloud Vision：作为 MIMO 2.5 的视觉模型备选 Provider。
- Local llama.cpp：作为 Cloud Text LLM 的本地文本模型备选 Provider。

## 4. API 与智能体映射

### multimodal_evidence_agent

主要场景：

- 现场图片证据分析
- 告警屏幕分析
- 铭牌信息抽取
- 媒体证据链生成

对应 API：

- 必填优先：MIMO 2.5
- 可选：OCR API
- 可选：Cloud Vision

相关工具：

- `media_lookup`
- `media_ocr`
- `media_mimo_analysis`
- `safety_guard`

### fault_diagnosis_agent

主要场景：

- 故障现象分析
- 规则型诊断
- 知识库检索
- 媒体证据辅助判断

对应 API：

- 当前主线：本地规则、知识库、知识图谱上下文
- 可选：Cloud Text LLM
- 可选输入：MIMO / OCR 已生成的媒体证据结果

相关工具：

- `diagnosis_rule_engine`
- `knowledge_search`
- `kg_business_context`
- `safety_guard`

### sop_planner_agent

主要场景：

- SOP 草稿生成
- 安全步骤组织
- 检修流程编排

对应 API：

- 当前主线：本地 SOP 规则和知识库
- 可选：Cloud Text LLM

相关工具：

- `sop_generator`
- `knowledge_search`
- `kg_business_context`
- `safety_guard`

### task_orchestration_agent

主要场景：

- 工单草稿生成
- 设备信息和历史记录读取
- 人工审批流程衔接

对应 API：

- 当前主线：本地业务规则
- 可选：Cloud Text LLM

相关工具：

- `device_lookup`
- `device_history`
- `record_center_lookup`
- `task_draft_creator`
- `safety_guard`
- `human_approval`

### knowledge_curator_agent

主要场景：

- 将诊断 / SOP / 工单 / 媒体证据沉淀为知识草稿
- 生成知识贡献草稿
- 生成证据追溯摘要

对应 API：

- 当前主线：本地诊断、SOP、工单、媒体证据和知识库
- 可选：Cloud Text LLM
- 可选输入：MIMO / OCR 已生成的证据结果

相关工具：

- `knowledge_search`
- `kg_business_context`
- `knowledge_contribution_draft_creator`
- `safety_guard`
- `human_approval`

### retrieval_qa_agent / model_gateway_chat

主要场景：

- 检修问答
- 模型网关文本对话预留
- 结构化摘要和抽取增强

对应 API：

- 可选：Cloud Text LLM
- 可选：Local llama.cpp

相关工具：

- `knowledge_search`
- `kg_business_context`
- `record_center_lookup`
- `model_gateway_chat`

### safety_guard_agent

主要场景：

- 电气检修安全边界提示
- 危险作业提醒
- 人工复核要求提示

对应 API：

- 当前主线：本地 `safety_rule_engine`
- 可选：Cloud Text LLM

相关工具：

- `safety_guard`
- `record_center_lookup`

## 5. 用户需要替换的占位符

必填优先：

```text
<FILL_MIMO_BASE_URL>
<FILL_MIMO_API_KEY>
```

推荐填写：

```text
<FILL_CLOUD_LLM_BASE_URL>
<FILL_CLOUD_LLM_API_KEY>
<FILL_CLOUD_LLM_MODEL>
<FILL_OCR_API_BASE_URL>
<FILL_OCR_API_KEY>
<FILL_OCR_API_MODEL>
```

可选增强：

```text
<FILL_CLOUD_VISION_BASE_URL>
<FILL_CLOUD_VISION_API_KEY>
<FILL_CLOUD_VISION_MODEL>
```

## 6. 填写后不要立刻宣称真实外呼完成

填写 `.env` 后，还需要后续 Task 22K 完成：

1. 在 `ExternalApiGateway` 中增加显式 real-run 模式。
2. 在 MIMO / OpenAI-compatible / OCR adapters 中实现真实 HTTP 调用。
3. 增加超时、错误处理、重试边界和脱敏日志验证。
4. 验证 `external_api_called=true` 只在真实外呼发生时出现。
5. 验证日志不保存 API Key、Authorization、base64 图片、本地文件路径。
6. 验证多模态证据中心能保存 `mocked=false` 的真实结果。
7. 验证 Agent tools 能读取真实 provider 结果并保持人工复核边界。
