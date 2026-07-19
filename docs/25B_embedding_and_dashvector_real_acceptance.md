# Task 25B Embedding 与 DashVector 真实验收

## DashScope Embedding

执行：`uv run python scripts/check_task25b_embedding_real.py --allow-real-api`

结果：PASSED。

- provider：`dashscope_openai_compatible`
- model：`text-embedding-v4`
- requested/returned dimension：1024/1024
- 单条：通过
- 10 条批量：通过
- 返回顺序：与输入顺序一致
- finite float：通过，NaN/Infinity 拒绝测试通过
- 中文语义探针：相关维修文本相似度高于无关文本
- 单批 usage：仅保存 token count 等安全统计
- Key、完整输入、完整向量：未输出

适配器使用异步 HTTP、并发信号量（默认 2）、429/5xx 指数退避、单批最多 10、`dimensions=1024`、`encoding_format=float`。query embedding 使用 TTL cache，文档 embedding 不使用永久内存缓存。

## DashVector

执行：`uv run python scripts/check_task25b_dashvector_real.py --allow-real-api`

结果：PASSED。

- endpoint：HTTPS Cluster Endpoint
- physical collection：`energy_kn_te_v4_1024_v1`
- dimension/metric/dtype：1024/cosine/float
- collection create or validate：通过
- stable provider-safe ID：通过（不使用 DashVector 不允许的冒号）
- 幂等重复 upsert：通过
- query：通过
- self-match：第一名
- raw cosine distance：0.0
- normalized similarity：1.0
- probe delete：通过
- PostgreSQL raw vector storage：无

DashVector HTTP 返回的 cosine `score` 按距离解释：越小越近；系统规范化为 `1 - raw_score / 2`，得到 0–1、越大越相似的统一分数，并同时保留 raw/normalized 分数。

## Collection 名称约束

DashVector 服务端将超过 32 字符的任务逻辑名拒绝为 `InvalidCollectionName (-2042)`。系统没有删除或覆盖旧集合，而是增加显式逻辑名/物理名映射。此项属于已知 provider compatibility deviation。

<!-- TASK25B_R1_BEGIN -->
## Task 25B-R1 controlled blind acceptance (2026-07-11T02:32:50.109583+00:00)

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- Corpus: 24 documents, 192 active chunks, 48 hard negatives.
- Adaptive blind metrics: R@5=1.000000, R@10=1.000000, MRR=0.981481, nDCG@10=0.986331, warm p95=704.712 ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
<!-- TASK25B_R1_END -->
