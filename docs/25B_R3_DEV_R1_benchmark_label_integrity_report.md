# Task 25B-R3-DEV-R1 Benchmark 标签完整性报告

生成时间：2026-07-12T10:28:50.763043+00:00

失败 v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 已只读冻结并保留，不得覆盖。新数据集 `task25b_r3_dev_r1_zh_v2` 与 v1 隔离，train/dev/test_v2={'train': 90, 'dev': 30, 'test_v2': 30}。Canary=`CANARY_PASSED`；唯一正式 v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 的质量门结果为 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。审批仍为开发工程审批，`expert_verified=false`。本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。

- v1 cases：150
- 分类：`{"ALARM_LABEL_ERROR": 14, "MODEL_LABEL_ERROR": 15, "VALID": 121}`
- stale expected IDs：0
- v2 SHA-256：`257a72892a54d7fd6caef4ae5e45f6b55b95731fcecbad5d2f467dad5f57a9e2`
- 标签修正：`{"grounded_document_section_query": 105, "grounded_alarm_code_query": 4, "grounded_model_query": 15, "grounded_fault_name_query": 11}`
- v1 未修改；所有修正只存在于 v2。

<!-- Task25B-R3-DEV-R2 -->

R2 confirms that each v2 test case has one relevant chunk, making fixed P@5 unsuitable as a universal single-relevant hard gate.
