# Task 25B-R2-U3-R3-DEV 中文工程 Benchmark 报告

生成时间：2026-07-12T09:17:19.761684+00:00

当前审批仅为开发工程审批；Codex 不是行业专家。 `expert_verified=false`、`second_reviewed=false`。当前默认语言为中文；英文资料保留但不启用，未删除。未使用机器翻译冒充官方中文。Pilot 仅使用 `pilot_r2`，默认 Partition 未改变，正式全量重建未执行。LoongArch 尚未实机验收。

上一轮因 Codex 所选模型容量错误中断，不是项目、DashScope、DashVector、Embedding、数据库或后端服务故障。恢复时沿用原质量门 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911`，未重复索引、未重复工程审批、未重建 Benchmark；原进程完成后直接审计其 600 条既有结果。最终质量判定：`DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。

## 数据集与完整性

- dataset：task25b_r2_u3_r3_dev_zh_v1
- cases：150
- modes：keyword, vector, hybrid, adaptive
- expected / actual：600 / 600
- missing：0
- duplicate：0
- execution errors：0
- 同数据集 run 数：1（无重复正式 run）
- Benchmark 状态：ENGINEERING_BENCHMARK_PASSED
- 统计：`{"cases": 150, "vector_heavy": 45, "no_answer": 15, "hard_negatives": 15, "safety": 15, "alarm_fault": 30, "engineering_verified": 150, "expert_verified": 0, "english_queries": 0}`

## 分模式真实指标

```json
{
  "keyword": {
    "recall_at_5": 0.1,
    "recall_at_10": 0.1,
    "precision_at_3": 0.1,
    "precision_at_5": 0.1,
    "mrr": 0.1,
    "ndcg_at_10": 0.1,
    "map": 0.1,
    "citation_valid": 0.233333,
    "citation_covered": 0.12,
    "english_leakage": 0.0,
    "non_chinese_leakage": 0.766667,
    "pending_leakage": 0.0,
    "marketing_leakage": 0.0,
    "superseded_leakage": 0.0,
    "fallback": 0.213333,
    "timeout": 0.0,
    "error": 0.0,
    "no_answer_precision": 0.46875,
    "no_answer_recall": 1.0,
    "no_answer_f1": 0.638298,
    "model_accuracy": 0.0,
    "alarm_fault_accuracy": 0.0,
    "p50_ms": 5434.236,
    "p95_ms": 8008.31,
    "p99_ms": 9650.276,
    "result_count": 150
  },
  "vector": {
    "recall_at_5": 0.313333,
    "recall_at_10": 0.36,
    "precision_at_3": 0.16,
    "precision_at_5": 0.142667,
    "mrr": 0.254238,
    "ndcg_at_10": 0.279511,
    "map": 0.254238,
    "citation_valid": 0.98,
    "citation_covered": 0.873333,
    "english_leakage": 0.0,
    "non_chinese_leakage": 0.02,
    "pending_leakage": 0.0,
    "marketing_leakage": 0.0,
    "superseded_leakage": 0.0,
    "fallback": 0.226667,
    "timeout": 0.0,
    "error": 0.0,
    "no_answer_precision": 0.483871,
    "no_answer_recall": 1.0,
    "no_answer_f1": 0.652174,
    "model_accuracy": 0.2,
    "alarm_fault_accuracy": 0.066667,
    "p50_ms": 5446.718,
    "p95_ms": 8260.006,
    "p99_ms": 9160.855,
    "result_count": 150
  },
  "hybrid": {
    "recall_at_5": 0.266667,
    "recall_at_10": 0.353333,
    "precision_at_3": 0.12,
    "precision_at_5": 0.133333,
    "mrr": 0.189849,
    "ndcg_at_10": 0.227692,
    "map": 0.189849,
    "citation_valid": 0.38,
    "citation_covered": 0.313333,
    "english_leakage": 0.0,
    "non_chinese_leakage": 0.62,
    "pending_leakage": 0.0,
    "marketing_leakage": 0.0,
    "superseded_leakage": 0.0,
    "fallback": 0.173333,
    "timeout": 0.0,
    "error": 0.0,
    "no_answer_precision": 0.6,
    "no_answer_recall": 1.0,
    "no_answer_f1": 0.75,
    "model_accuracy": 0.133333,
    "alarm_fault_accuracy": 0.066667,
    "p50_ms": 5269.02,
    "p95_ms": 8372.81,
    "p99_ms": 9285.669,
    "result_count": 150
  },
  "adaptive": {
    "recall_at_5": 0.106667,
    "recall_at_10": 0.106667,
    "precision_at_3": 0.102222,
    "precision_at_5": 0.101333,
    "mrr": 0.102222,
    "ndcg_at_10": 0.103333,
    "map": 0.102222,
    "citation_valid": 0.366667,
    "citation_covered": 0.253333,
    "english_leakage": 0.0,
    "non_chinese_leakage": 0.633333,
    "pending_leakage": 0.0,
    "marketing_leakage": 0.0,
    "superseded_leakage": 0.0,
    "fallback": 0.213333,
    "timeout": 0.0,
    "error": 0.0,
    "no_answer_precision": 0.46875,
    "no_answer_recall": 1.0,
    "no_answer_f1": 0.638298,
    "model_accuracy": 0.0,
    "alarm_fault_accuracy": 0.0,
    "p50_ms": 5403.818,
    "p95_ms": 7808.264,
    "p99_ms": 9080.533,
    "result_count": 150
  }
}
```

## Pilot 质量门

- 原始脚本结果：DEVELOPMENT_ENGINEERING_PILOT_FAIL
- 最终规范化结果：DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED
- 门禁检查：`{"recall_at_5": false, "recall_at_10": false, "mrr": false, "ndcg_at_10": false, "precision_at_5": false, "citation_validity": false, "citation_coverage": false, "no_answer_f1": false, "model_accuracy": false, "english_leakage": true, "non_chinese_leakage": false, "pending_leakage": true, "marketing_leakage": true, "superseded_leakage": true, "warm_p95": false, "error_rate": true}`
- 工程门禁通过：False
- expert_verified：false
- 专家验收：否
- 生产就绪：否

<!-- TASK25B_R3_DEV_R1_BEGIN -->
## Task 25B-R3-DEV-R1 检索治理更新

- v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 失败且保留；v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 独立保存。
- Benchmark 数据集状态：`BENCHMARK_DATASET_READY`；质量门状态：`QUALITY_GATE_FAILED`，二者不得混淆。
- Scope：`chinese_engineering_pilot_r2`；Canary：`CANARY_PASSED`；正式 v2：`DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- Pilot 对账：1262/1262，re-embedded=0、re-upserted=0。
- 工程审批不等于专家验证；正式全量重建未执行；不打包、不提交 Git。
<!-- TASK25B_R3_DEV_R1_END -->
