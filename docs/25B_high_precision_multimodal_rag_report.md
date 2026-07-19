# Task 25B 高精度多模态 RAG 报告

## 结论

Task 25B 当前结论为 **PARTIAL / QUALITY_GATE_FAILED**，不是完全通过。

- DashScope `text-embedding-v4` 真实调用通过，返回维度真实验证为 1024。
- DashVector 真实创建/校验、幂等 upsert、query、self-match、删除探针通过。
- 8 个 `Task25B_` approved chunk 完成受控真实索引，未执行正式知识全量重建。
- 80 条 engineering-controlled 用例和 30 条正式知识派生 draft 已落 PostgreSQL。
- `descriptor_based_cross_modal` 的图到手册、图到案例和相似媒体受控链路通过；未使用 raw image embedding。
- 检索 test split 的质量门禁未通过，因此不得声明 Task 25B fully complete。

## 架构

主链路保持 `FastAPI -> service -> repository -> SQLAlchemy/PostgreSQL`。PostgreSQL 是事实源，DashVector 只保存向量和最小召回元数据。向量命中必须回 PostgreSQL 校验文档 `approved/active/parsed` 和 chunk `active` 状态。

新增核心服务：

- `QueryUnderstandingService`
- `DashScopeOpenAICompatibleEmbeddingAdapter`
- `SemanticChunker`
- `FeatureFusionReranker`
- `CitationValidationService`
- `MultimodalRetrievalService`
- `RetrievalEvaluationService`

## 真实链路状态

真实验收证据位于 `.runtime/task25b/`。输出不含 Key、Authorization、原始向量、完整用户文档或 base64 图片。

DashVector 官方限制 Collection 名为 3–32 字符，而任务给定的两个逻辑名超过 32 字符。系统保留逻辑版本名：

- `energy_maintenance_knowledge_te_v4_1024_v1`
- `energy_maintenance_media_te_v4_1024_v1`

实际 provider-safe 物理名为：

- `energy_kn_te_v4_1024_v1`
- `energy_media_te_v4_1024_v1`

该差异是已知外部约束，不作为“完全符合原名”报告。

## 质量门禁

真实 test split 共 20 个用例、80 个 mode-result。`hybrid_rerank` 结果：Recall@5 0.90、Recall@10 0.90、MRR 0.58、nDCG@10 0.654741、citation validity 1.00、filter leakage 0、p95 4362.713 ms。Recall@10、MRR、nDCG@10 和 p95 未达目标。

`rerank` 没有比 hybrid 下降超过 1%，因此本次没有触发精排自动禁用；但它也没有形成可证明的质量提升。

## 安全与边界

- 高风险电气建议保留人工确认。
- 文档内容视为不可信检索数据，不得覆盖系统指令。
- `TASK25B_ALLOW_FULL_REINDEX=false`，全量重建脚本被门禁拒绝。
- Record Center 既有性能 P1 保留，本任务未伪装修复。
- LoongArch + Kylin 未做实机验收；没有新增 GPU、CUDA、Docker、pgvector、Neo4j、FAISS 或本地大模型依赖。
- 本任务未打包，未执行 Git add/commit/reset/clean/restore。

<!-- TASK25B_R1_BEGIN -->
## Task 25B-R1 controlled blind acceptance (2026-07-11T02:32:50.109583+00:00)

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- Corpus: 24 documents, 192 active chunks, 48 hard negatives.
- Adaptive blind metrics: R@5=1.000000, R@10=1.000000, MRR=0.981481, nDCG@10=0.986331, warm p95=704.712 ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
<!-- TASK25B_R1_END -->


<!-- TASK25B_R2_BEGIN -->
## Task 25B-R2 正式知识 Pilot 状态

- 状态：`BLOCKED_CONFIG`；正式可用语料只有 6 份文档、11 个 active Chunk，未达到 300。
- 独立 Pilot Collection `energy_kn_te_v4_1024_pilot1` 创建被服务商 2 个 Collection 配额阻断；未删除或复用现有 Collection。
- 已生成 150 条 `draft` 候选；`expert_verified=0`，未冻结或运行 `official_pilot_test_v1`。
- 默认 Collection 与 `keyword` 策略未改变；`TASK25B_ALLOW_FULL_REINDEX=false`，全量重建决策为 NO-GO。
- 本任务未打包、未提交 Git；LoongArch/Kylin 仍未实机验收。
<!-- TASK25B_R2_END -->
