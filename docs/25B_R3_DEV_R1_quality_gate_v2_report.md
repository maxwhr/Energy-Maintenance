# Task 25B-R3-DEV-R1 v2 质量门报告

生成时间：2026-07-12T10:28:50.763043+00:00

失败 v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 已只读冻结并保留，不得覆盖。新数据集 `task25b_r3_dev_r1_zh_v2` 与 v1 隔离，train/dev/test_v2={'train': 90, 'dev': 30, 'test_v2': 30}。Canary=`CANARY_PASSED`；唯一正式 v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 的质量门结果为 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。审批仍为开发工程审批，`expert_verified=false`。本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。

- test_v2 cases/results：30/120
- checks：`{"recall_at_5": true, "recall_at_10": true, "precision_at_5": false, "mrr": true, "ndcg_at_10": true, "citation_validity": true, "citation_coverage": true, "no_answer_f1": true, "model_accuracy": false, "alarm_accuracy": true, "all_leakage_zero": true, "keyword_external_zero": true, "keyword_p95": true, "warm_p95": true, "error_rate": true, "timeout_rate": true, "adaptive_recall_relative": true, "adaptive_mrr_relative": true, "adaptive_ndcg_relative": true, "vector_heavy_gain": false}`

```json
{
  "keyword": {
    "recall_at_5": 0.966667,
    "recall_at_10": 0.966667,
    "precision_at_5": 0.273333,
    "mrr": 0.95,
    "ndcg_at_10": 0.954364,
    "map": 0.95,
    "citation_valid": 1.0,
    "citation_coverage": 1.0,
    "no_answer_f1": 1.0,
    "model_accuracy": 0.0,
    "alarm_accuracy": 1.0,
    "non_chinese_leakage": 0.0,
    "pending_marketing_superseded_leakage": 0.0,
    "p50_ms": 237.492,
    "p95_ms": 783.712,
    "p99_ms": 983.729,
    "fallback_rate": 0.1,
    "timeout_rate": 0.0,
    "error_rate": 0.0,
    "external_api_calls": 0
  },
  "vector": {
    "recall_at_5": 0.966667,
    "recall_at_10": 0.966667,
    "precision_at_5": 0.273333,
    "mrr": 0.95,
    "ndcg_at_10": 0.954364,
    "map": 0.95,
    "citation_valid": 1.0,
    "citation_coverage": 1.0,
    "no_answer_f1": 1.0,
    "model_accuracy": 0.0,
    "alarm_accuracy": 1.0,
    "non_chinese_leakage": 0.0,
    "pending_marketing_superseded_leakage": 0.0,
    "p50_ms": 859.677,
    "p95_ms": 1440.539,
    "p99_ms": 2906.359,
    "fallback_rate": 0.1,
    "timeout_rate": 0.0,
    "error_rate": 0.0,
    "external_api_calls": 30
  },
  "hybrid": {
    "recall_at_5": 0.966667,
    "recall_at_10": 0.966667,
    "precision_at_5": 0.273333,
    "mrr": 0.95,
    "ndcg_at_10": 0.954364,
    "map": 0.95,
    "citation_valid": 1.0,
    "citation_coverage": 1.0,
    "no_answer_f1": 1.0,
    "model_accuracy": 0.0,
    "alarm_accuracy": 1.0,
    "non_chinese_leakage": 0.0,
    "pending_marketing_superseded_leakage": 0.0,
    "p50_ms": 773.651,
    "p95_ms": 1309.551,
    "p99_ms": 1329.779,
    "fallback_rate": 0.1,
    "timeout_rate": 0.0,
    "error_rate": 0.0,
    "external_api_calls": 30
  },
  "adaptive": {
    "recall_at_5": 0.966667,
    "recall_at_10": 0.966667,
    "precision_at_5": 0.273333,
    "mrr": 0.95,
    "ndcg_at_10": 0.954364,
    "map": 0.95,
    "citation_valid": 1.0,
    "citation_coverage": 1.0,
    "no_answer_f1": 1.0,
    "model_accuracy": 0.0,
    "alarm_accuracy": 1.0,
    "non_chinese_leakage": 0.0,
    "pending_marketing_superseded_leakage": 0.0,
    "p50_ms": 240.303,
    "p95_ms": 1079.851,
    "p99_ms": 1243.368,
    "fallback_rate": 0.1,
    "timeout_rate": 0.0,
    "error_rate": 0.0,
    "external_api_calls": 3
  }
}
```

未通过项不得通过降阈值、删除 case 或覆盖 run 处理。

<!-- Task25B-R3-DEV-R2 -->

R2 froze v2 as a read-only failed baseline. It was neither overwritten nor rerun.
