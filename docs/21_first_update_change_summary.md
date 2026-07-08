# Energy-Maintenance 第一次修改说明

## 1. 修改背景

原项目已经具备 FastAPI 后端、Vue3 前端、PostgreSQL 数据库、知识库上传解析、关键词检索、问答记录、模型网关等基础能力。

本次修改主要解决以下问题：

- 项目只有关键词检索和规则回答，还不是完整的 RAG 问答链路。
- 已有华为 SUN2000 手册和图片集未纳入项目知识库样例。
- 检索结果没有向量化增强，语义召回能力较弱。
- 云端大模型增强回答未真正接入到检索问答闭环。
- 前端检修问答页没有稳定的流式输出显示。

本次修改仍保持项目第一版范围不变：只面向华为、阳光电源光伏逆变器检修知识问答与辅助作业。

## 2. 本次主要修改内容

### 2.1 合并华为 SUN2000 手册与图片集

新增项目内样例资料：

- `backend/storage/samples/huawei_sun2000_196ktl_h0_user_manual_rag.md`
- `backend/storage/samples/huawei_sun2000_196ktl_h0_images/`

图片集已复制进项目，共 142 个图片文件：

- PNG：135 个
- JP2：7 个

Markdown 手册中的图片引用已改为项目内相对路径，便于后续上传 GitHub 后继续保持可追溯。

### 2.2 增加本地轻量向量化能力

新增文件：

- `backend/app/services/text_vector_service.py`

实现内容：

- 对中文内容生成二字、三字片段。
- 对英文、型号、数字等生成词项。
- 生成轻量稀疏文本向量。
- 向量结果保存到 `knowledge_chunks.metadata_json.text_vector`。
- 新解析的知识切片会自动标记为 `embedding_status = embedded`。

说明：

本次未引入 `pgvector`、外部 embedding 模型或重型依赖，目的是保证当前本地环境和后续 LoongArch + Kylin 部署路线更容易运行。

### 2.3 检索从关键词升级为“关键词 + 向量召回”

修改文件：

- `backend/app/repositories/retrieval_repository.py`
- `backend/app/services/retrieval_service.py`
- `backend/app/schemas/retrieval.py`

实现内容：

- 保留原有 PostgreSQL 关键词检索。
- 新增向量候选 chunk 召回。
- 查询时计算问题向量，与知识切片向量做相似度匹配。
- 合并关键词分数和向量分数后排序。
- 新增请求开关 `enable_vector_search`，默认启用。

效果：

问答时不再只依赖字面关键词命中，能够根据相近语义召回相关手册片段。

### 2.4 RAG Prompt 增强

修改文件：

- `backend/app/services/model_prompt_builder.py`
- `backend/app/services/retrieval_service.py`

实现内容：

- 大模型增强回答时，不再只传短引用。
- Prompt 中加入真实召回到的 `retrieved_chunks` 正文片段。
- 继续保留 references 约束，要求模型不得编造来源、页码、chunk 或厂家要求。

当前 RAG 链路为：

```text
用户问题
-> PostgreSQL 知识库检索
-> 关键词 + 向量召回
-> 返回真实 retrieved_chunks / references
-> 构造 RAG Prompt
-> 调用云端大模型
-> 输出检修建议
-> 保存 qa_records 和 model_call_logs
```

### 2.5 接入阿里云百炼 OpenAI 兼容模型

修改文件：

- `backend/app/services/model_adapters/base.py`
- `backend/app/services/model_adapters/cloud_openai_adapter.py`
- `backend/app/services/model_gateway_service.py`
- `backend/app/services/model_enhancement_service.py`

实现内容：

- 使用项目已有的 `cloud_openai` 模型网关路线。
- 支持 OpenAI-compatible Chat Completions。
- 支持阿里云百炼兼容地址。
- 支持普通非流式调用。
- 支持 `stream: true` 流式调用。
- 模型调用记录写入 `model_call_logs`。
- 不向前端、日志或响应暴露 API Key。

本地配置项位于 `backend/.env`：

```env
CLOUD_LLM_ENABLED=true
CLOUD_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode
CLOUD_LLM_API_KEY=不要提交到GitHub
CLOUD_LLM_MODEL=qwen-plus
```

注意：`backend/.env` 中的真实 API Key 不应提交到 GitHub。

### 2.6 新增检索问答流式接口

修改文件：

- `backend/app/api/routes/retrieval.py`
- `backend/app/services/retrieval_service.py`

新增接口：

```text
POST /api/retrieval/query/stream
```

接口返回类型：

```text
text/event-stream
```

流式事件包括：

- `retrieval`：先返回检索结果、references、retrieved_chunks 等基础信息。
- `delta`：大模型回答片段。
- `done`：最终完整回答和最终记录。
- `error`：流式调用错误。

### 2.7 前端检修问答页接入流式输出

修改文件：

- `frontend/src/api/retrieval.ts`
- `frontend/src/views/assistant/Chat.vue`

实现内容：

- 新增 `streamRetrievalApi`。
- 使用 `fetch` 读取 `text/event-stream`。
- 收到 `delta` 事件后逐段追加到回答区域。
- 修复前端响应式显示问题，避免收到流式片段但页面不刷新的情况。
- 检修问答页默认请求 `cloud_openai`，并启用模型增强。

## 3. 新增脚本

### 3.1 导入华为 SUN2000 样例手册

新增文件：

- `backend/scripts/import_huawei_sun2000_sample_manual.py`

作用：

- 将项目内华为 SUN2000 RAG 版 Markdown 导入 PostgreSQL。
- 自动解析、切片、向量化。
- 将样例文档设置为 `approved`，方便问答检索。

已验证导入结果：

- 文档状态：`parsed`
- 审核状态：`approved`
- chunk 数量：151
- 已向量化 chunk：151

### 3.2 批量补齐旧知识切片向量

新增文件：

- `backend/scripts/vectorize_knowledge_chunks.py`

作用：

- 对数据库中已有但未向量化的 `knowledge_chunks` 生成向量。
- 更新 `embedding_status = embedded`。

### 3.3 更新 Demo 知识脚本

修改文件：

- `backend/scripts/seed_demo_knowledge.py`

修改内容：

- Demo 知识切片生成时同步生成轻量向量。
- Demo chunk 默认标记为 `embedded`。

## 4. 验证结果

### 4.1 后端编译检查

执行命令：

```powershell
cd D:\Energy-Maintenance\Energy-Maintenance\backend
.\.venv\Scripts\python.exe -m compileall app scripts
```

结果：

```text
passed
```

### 4.2 前端构建检查

执行命令：

```powershell
cd D:\Energy-Maintenance\Energy-Maintenance\frontend
npm run build
```

结果：

```text
passed
```

### 4.3 样例手册导入验证

执行脚本：

```powershell
cd D:\Energy-Maintenance\Energy-Maintenance\backend
.\.venv\Scripts\python.exe scripts\import_huawei_sun2000_sample_manual.py
```

结果：

```text
Imported sample manual. chunks=151
```

### 4.4 真实云模型调用验证

模型配置：

```text
provider: cloud_openai
model: qwen-plus
```

验证结果：

```text
real cloud model call: passed
stream output: passed
```

### 4.5 完整 RAG 流式链路验证

验证问题：

```text
SUN2000 维护前需要注意哪些安全事项？
```

验证结果：

```text
retrieval_events: 1
delta_events: 171
done_events: 1
error_events: 0
references: 3
retrieved_chunks: 3
model_enhanced: True
model_provider: cloud_openai
model_name: qwen-plus
```

说明：

- `references > 0` 表示命中了真实知识来源。
- `retrieved_chunks > 0` 表示大模型回答前已经检索到真实知识切片。
- `delta_events > 0` 表示流式输出已生效。
- `model_enhanced = True` 表示回答经过真实大模型增强。

## 5. 相比原项目的变化总结

| 模块 | 原项目状态 | 本次修改后 |
|---|---|---|
| 知识资料 | 没有合并当前华为手册和图片集 | 已合并 SUN2000 手册和 142 个图片文件 |
| 检索方式 | PostgreSQL 关键词检索为主 | 关键词检索 + 本地轻量向量召回 |
| 向量化 | chunk 默认为 pending | 新解析 chunk 自动生成向量并标记 embedded |
| RAG | 没有完整大模型 RAG 闭环 | retrieved_chunks 进入大模型 Prompt |
| 大模型 | 默认 rule_based | 已接入阿里云百炼 qwen-plus |
| 流式输出 | 无前端稳定流式展示 | 新增 SSE 流式接口和前端逐段显示 |
| 记录追踪 | 已有 qa_records / model_call_logs 基础 | RAG 流式问答会保存 QA 记录和模型调用记录 |
| 安全 | API Key 需人工配置 | 不在响应和日志中暴露 API Key |

## 6. 提交 GitHub 前注意事项

### 6.1 不要提交真实 API Key

请确认不要把以下文件中的真实密钥提交到 GitHub：

```text
backend/.env
```

如果需要给组长说明配置方式，应提交：

```text
backend/.env.example
```

并在文档中写占位符：

```env
CLOUD_LLM_API_KEY=<your_api_key>
```

### 6.2 建议检查 Git 状态

提交前执行：

```powershell
git status --short
```

重点确认没有把真实密钥、临时文件、虚拟环境、数据库文件提交上去。

### 6.3 图片集文件较多

本次加入了 142 个图片文件。若 GitHub 仓库体积有限，可以让组长确认是否接受图片集直接入库。

## 7. 当前已知限制

- 当前向量化是轻量稀疏文本向量，不是 `pgvector` + embedding 模型。
- 图片理解主要依赖 Markdown 中已有的 OCR 文本和图片说明，不是视觉大模型直接识图。
- 云端大模型依赖阿里云百炼 API Key 和网络环境。
- 如果后端未重启，`.env` 中的新模型配置不会生效。

## 8. 建议后续任务

1. 增加前端模型状态提示，显示当前是否启用云模型。
2. 增加 RAG 流式接口的自动化测试脚本。
3. 增加 `.env.example` 中阿里云百炼配置示例。
4. 后续如有需要，可升级为 `pgvector + embedding` 的正式向量检索方案。
5. 如要让系统直接理解图片内容，可单独规划 OCR 或视觉模型增强任务。
