# Task 25B-R1 Failure Analysis Report

> test_v1 已暴露，只用于误差分析和防回归，不再作为独立盲测集。

## Scope

- Cases analyzed: 20
- Source snapshot SHA-256: `e1f2ce98782de927f2c6b9615e4ce639cc90814366c8a727f5150eeef992e2e9`
- JSON: `.runtime\task25b_r1\failure_analysis.json`
- CSV: `.runtime\task25b_r1\failure_analysis.csv`

## Failure classes

| Class | Count |
|---|---:|
| FUSION_DEGRADATION | 8 |
| LATENCY_DASHVECTOR | 20 |
| LATENCY_EMBEDDING | 3 |
| NO_ANSWER_FALSE_POSITIVE | 2 |
| RERANK_NO_OP | 12 |

## Category summary

| Category | Primary observations |
|---|---|
| OCR | LATENCY_DASHVECTOR=2, RERANK_NO_OP=2 |
| 历史案例 | LATENCY_DASHVECTOR=2, LATENCY_EMBEDDING=1, RERANK_NO_OP=2 |
| 安全操作 | FUSION_DEGRADATION=2, LATENCY_DASHVECTOR=2 |
| 干扰过滤 | LATENCY_DASHVECTOR=2, RERANK_NO_OP=2 |
| 手册章节 | FUSION_DEGRADATION=2, LATENCY_DASHVECTOR=2 |
| 故障现象 | FUSION_DEGRADATION=2, LATENCY_DASHVECTOR=2 |
| 故障码 | LATENCY_DASHVECTOR=2 |
| 无答案 | LATENCY_DASHVECTOR=2, LATENCY_EMBEDDING=1, NO_ANSWER_FALSE_POSITIVE=2, RERANK_NO_OP=2 |
| 视觉描述 | FUSION_DEGRADATION=2, LATENCY_DASHVECTOR=2, LATENCY_EMBEDDING=1, RERANK_NO_OP=2 |
| 设备型号 | LATENCY_DASHVECTOR=2, RERANK_NO_OP=2 |

## Root causes

1. Vector candidates were admitted without a dev-calibrated usefulness threshold and could demote stronger keyword evidence.
2. The original feature reranker frequently preserved the hybrid ordering, so its existence did not demonstrate ranking gain.
3. Exact device-model and fault-code evidence needs hard priority before soft semantic fusion.
4. External embedding and DashVector calls dominated latency; warm reuse, bounded caching and timeout fallback are required.
5. No-answer cases need explicit abstention metrics rather than being treated as ordinary empty relevance lists.

## Integrity

No test_v2 labels were created or inspected during this analysis.
