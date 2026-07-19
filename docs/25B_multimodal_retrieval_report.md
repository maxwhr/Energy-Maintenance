# Task 25B 多模态检索报告

## 能力边界

能力标签固定为 `descriptor_based_cross_modal`。原始图片不直接生成 image embedding；`raw_image_embedding=false`。

媒体被转换为规范描述符：设备型号、故障码、部件、OCR 可见文字、故障现象、安全风险和其他视觉特征。该文本描述符使用真实 `text-embedding-v4` 生成 1024 维向量。

## 检索能力

- 图片到手册：描述符向量查询 knowledge collection，并回 PostgreSQL 校验。
- 图片到故障案例：限定 `fault_case` 查询并回查。
- 相似媒体：融合 descriptor vector、OCR token、pHash、dHash、设备型号 exact、故障码 exact 和 component overlap。

受控验收通过，图到手册、图到案例和相似媒体均返回结果。相似媒体示例汇总分数为 0.999405，所有分项均单独返回，且保留 `human_review_required=true`。

## 感知哈希实现边界

运行时不强制新增 Pillow 等 LoongArch 未确认的 native dependency。服务支持：

1. 可信上游预计算的 pHash/dHash；
2. 环境已提供 Pillow 时的 DCT pHash/dHash。

本次受控 PNG fixture 使用可信预计算哈希验证融合链路。对于未带预计算哈希且运行环境没有 Pillow 的真实媒体，服务明确阻塞该特征生成，不以普通文件 hash 冒充感知哈希。

## 安全

API/前端不返回文件绝对路径、base64、Key、Authorization 或原始向量。视觉/OCR 结果均为辅助证据，必须人工审核后才能进入高风险检修决策。

<!-- TASK25B_R1_BEGIN -->
## Task 25B-R1 controlled blind acceptance (2026-07-11T02:32:50.109583+00:00)

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- Corpus: 24 documents, 192 active chunks, 48 hard negatives.
- Adaptive blind metrics: R@5=1.000000, R@10=1.000000, MRR=0.981481, nDCG@10=0.986331, warm p95=704.712 ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
<!-- TASK25B_R1_END -->
