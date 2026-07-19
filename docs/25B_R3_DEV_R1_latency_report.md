# Task 25B-R3-DEV-R1 检索延迟报告

生成时间：2026-07-12T10:28:50.763043+00:00

失败 v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 已只读冻结并保留，不得覆盖。新数据集 `task25b_r3_dev_r1_zh_v2` 与 v1 隔离，train/dev/test_v2={'train': 90, 'dev': 30, 'test_v2': 30}。Canary=`CANARY_PASSED`；唯一正式 v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 的质量门结果为 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。审批仍为开发工程审批，`expert_verified=false`。本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。

## Dev 调优

```json
{
  "generated_at": "2026-07-12T10:20:18.397447+00:00",
  "tuning_split": "train+dev",
  "test_v2_used_for_tuning": false,
  "changes": {
    "scope": "chinese_engineering_pilot_r2",
    "keyword_candidate_limit": 100,
    "boilerplate_ngrams_removed": true,
    "exact_heading_boost": 80.0,
    "vector_top_k_canary": 50,
    "vector_exact_anchor": true,
    "query_embedding_cache": true,
    "http_keep_alive": true,
    "vector_timeout_seconds": 3.5
  },
  "dev_keyword": {
    "recall_at_5": 0.966667,
    "mrr": 0.908333,
    "p95_ms": 885.051,
    "external_api_call_count": 0
  },
  "canary_status": "CANARY_PASSED",
  "quality_thresholds_lowered": false,
  "expected_labels_used_in_runtime_rules": false
}
```

## 正式 v2

```json
{
  "keyword": {
    "p50_ms": 237.492,
    "p95_ms": 783.712,
    "p99_ms": 983.729,
    "timeout_rate": 0.0,
    "error_rate": 0.0
  },
  "vector": {
    "p50_ms": 859.677,
    "p95_ms": 1440.539,
    "p99_ms": 2906.359,
    "timeout_rate": 0.0,
    "error_rate": 0.0
  },
  "hybrid": {
    "p50_ms": 773.651,
    "p95_ms": 1309.551,
    "p99_ms": 1329.779,
    "timeout_rate": 0.0,
    "error_rate": 0.0
  },
  "adaptive": {
    "p50_ms": 240.303,
    "p95_ms": 1079.851,
    "p99_ms": 1243.368,
    "timeout_rate": 0.0,
    "error_rate": 0.0
  }
}
```
