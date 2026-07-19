# Task 25B-R3-DEV-R1 检索作用域治理报告

生成时间：2026-07-12T10:28:50.763043+00:00

失败 v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 已只读冻结并保留，不得覆盖。新数据集 `task25b_r3_dev_r1_zh_v2` 与 v1 隔离，train/dev/test_v2={'train': 90, 'dev': 30, 'test_v2': 30}。Canary=`CANARY_PASSED`；唯一正式 v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 的质量门结果为 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。审批仍为开发工程审批，`expert_verified=false`。本任务未重新索引 1,262 个向量，未修改 default Partition，未执行正式全量重建；LoongArch 未实机验收，不打包、不提交 Git。

## Scope

```json
{
  "generated_at": "2026-07-12T09:46:50.280603+00:00",
  "scope": {
    "scope_id": "chinese_engineering_pilot_r2",
    "corpus_type": "development_engineering_pilot",
    "normalized_language": "zh-CN",
    "allowed_document_ids": [
      "12703ebb-4860-4a8a-bed3-11734dbcdfa5",
      "1666856f-bcb6-43a4-b434-1ff057b67cbc",
      "2a1a0210-0528-4975-8eb8-97883f6cc2a0",
      "2cc85307-e1f3-4382-896f-2cdae645af11",
      "2ee5665d-5a65-48dc-9e1e-1aaecd73a121",
      "2f6e8766-df74-4e31-abd4-c4b806a538bb",
      "4a47e05a-b45c-4e64-b75b-4ceb3ff6d0c5",
      "584adeaf-7221-4ab6-b191-749ce3c99c57",
      "5900d4bc-5170-4dfb-8c08-de572d2286a8",
      "6ae25eec-2f61-453a-9b08-f4f1c31cb382",
      "7be3e048-f732-41ff-b0fb-c14719a77e2c",
      "7ebafad0-1194-4400-b75a-6f8d3d18197b",
      "ae3942d8-0ae3-4282-8e05-3ea4a8d08e75",
      "c50295a3-1f71-40a6-b621-5f1ab3a4b554",
      "c78406bf-0830-4553-8036-dc9469a28eb3",
      "fbb02382-88d0-4f5a-a8fb-56404a8b7cf2"
    ],
    "required_document_status": "approved",
    "required_chunk_status": "active",
    "required_approval_mode": [
      "development_engineering_auto",
      "human_expert_approval"
    ],
    "approved_for_pilot": true,
    "current_version_only": true,
    "collection_name": "energy_kn_te_v4_1024_v1",
    "partition_name": "pilot_r2",
    "include_unknown_language": false,
    "include_alternate_language": false,
    "include_test_fixture": false,
    "include_marketing": false,
    "include_superseded": false
  },
  "eligible_chunks": 1262,
  "checks": {
    "immutable": true,
    "scope_id": true,
    "document_count": true,
    "chunk_count": true,
    "chinese_only": true,
    "pilot_only": true,
    "current_only": true,
    "no_alternate": true,
    "no_test_fixture": true,
    "no_marketing": true,
    "collection": true
  },
  "passed": true
}
```

Keyword、Vector、Hybrid、Adaptive 及 fallback 均使用同一不可变 Scope；未知语言、英文备用、测试资料、营销资料和 superseded 资料在候选 SQL/PG 回查阶段排除。
