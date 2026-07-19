# Task 25B-R3-DEV-R1 Adaptive Scope 报告

生成时间：2026-07-12T10:28:50.763043+00:00

失败 v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 已只读冻结并保留，不得覆盖。新数据集 `task25b_r3_dev_r1_zh_v2` 与 v1 隔离，train/dev/test_v2={'train': 90, 'dev': 30, 'test_v2': 30}。Canary=`CANARY_PASSED`；唯一正式 v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 的质量门结果为 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。审批仍为开发工程审批，`expert_verified=false`。本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。

Adaptive 路由、exact model/alarm、semantic hybrid 和 timeout fallback 均保留 `chinese_engineering_pilot_r2`。

Canary 分模式：
```json
{
  "keyword": {
    "result_count": 20,
    "recall_at_5": 0.95,
    "recall_at_10": 0.95,
    "mrr": 0.95,
    "ndcg_at_10": 0.95,
    "citation_validity": 1.0,
    "citation_coverage": 1.0,
    "non_chinese_leakage": 0.0,
    "missing_language_leakage": 0.0,
    "p50_ms": 456.887,
    "p95_ms": 826.194,
    "fallback_rate": 0.1,
    "external_api_calls": 0
  },
  "vector": {
    "result_count": 20,
    "recall_at_5": 0.95,
    "recall_at_10": 0.95,
    "mrr": 0.925,
    "ndcg_at_10": 0.931546,
    "citation_validity": 1.0,
    "citation_coverage": 1.0,
    "non_chinese_leakage": 0.0,
    "missing_language_leakage": 0.0,
    "p50_ms": 840.662,
    "p95_ms": 1583.589,
    "fallback_rate": 0.1,
    "external_api_calls": 20
  },
  "hybrid": {
    "result_count": 20,
    "recall_at_5": 0.95,
    "recall_at_10": 0.95,
    "mrr": 0.9,
    "ndcg_at_10": 0.913093,
    "citation_validity": 1.0,
    "citation_coverage": 1.0,
    "non_chinese_leakage": 0.0,
    "missing_language_leakage": 0.0,
    "p50_ms": 921.731,
    "p95_ms": 1724.154,
    "fallback_rate": 0.1,
    "external_api_calls": 20
  },
  "adaptive": {
    "result_count": 20,
    "recall_at_5": 0.95,
    "recall_at_10": 0.95,
    "mrr": 0.925,
    "ndcg_at_10": 0.931546,
    "citation_validity": 1.0,
    "citation_coverage": 1.0,
    "non_chinese_leakage": 0.0,
    "missing_language_leakage": 0.0,
    "p50_ms": 276.31,
    "p95_ms": 1086.684,
    "fallback_rate": 0.1,
    "external_api_calls": 8
  }
}
```
