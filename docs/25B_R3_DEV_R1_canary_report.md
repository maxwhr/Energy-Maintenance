# Task 25B-R3-DEV-R1 Canary 报告

生成时间：2026-07-12T10:28:50.763043+00:00

失败 v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 已只读冻结并保留，不得覆盖。新数据集 `task25b_r3_dev_r1_zh_v2` 与 v1 隔离，train/dev/test_v2={'train': 90, 'dev': 30, 'test_v2': 30}。Canary=`CANARY_PASSED`；唯一正式 v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 的质量门结果为 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。审批仍为开发工程审批，`expert_verified=false`。本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。

- 最终状态：`CANARY_PASSED`
- cases/modes：20/['keyword', 'vector', 'hybrid', 'adaptive']
- 检查：`{"expected_label_validity": true, "non_chinese_zero": true, "missing_language_zero": true, "scope_validation_zero": true, "keyword_external_api_zero": true, "keyword_recall_at_5": true, "vector_recall_at_5": true, "citation_validity": true, "keyword_p95": true, "vector_hybrid_adaptive_p95": true, "error_zero": true}`
- 前四轮失败证据保留为 canary_attempt_1..4.json。
