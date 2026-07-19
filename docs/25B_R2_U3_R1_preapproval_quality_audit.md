# Task 25B-R2-U3-R1 正式文档批准前质量审计

## 结论

本次只生成审核建议和 `engineering_candidate` Benchmark 缺口候选，没有批准文档、写入 expert review、调用 Embedding/DashVector 或执行 Pilot 索引。审计对象为 34 份数据库 pending 官方文档及 5 份仅检查的 `NEEDS_METADATA` 候选；1,161 个数据库 Chunk 全部纳入统计。

## A. 推荐优先批准

- `12703ebb-4860-4a8a-bed3-11734dbcdfa5` — LUNA2000 FAQ - 如何回收废旧电池 — RECOMMEND_APPROVE
- `2cc85307-e1f3-4382-896f-2cdae645af11` — SUN2000 FAQ - WiFi忘记密码 — RECOMMEND_APPROVE
- `2f6e8766-df74-4e31-abd4-c4b806a538bb` — SUN2000 FAQ - 光伏逆变器不开机 — RECOMMEND_APPROVE
- `4d3c2a7a-acef-4fca-b479-35ec331fe75b` — SUN2000 FAQ - If the WiFi antenna or DC, AC,…ther supplies? — RECOMMEND_APPROVE
- `528dd661-7bb4-4f99-9d30-29974aec7dfc` — LUNA2000 FAQ - How Do I Recycle Used Batteries? — RECOMMEND_APPROVE
- `584adeaf-7221-4ab6-b191-749ce3c99c57` — LUNA2000 FAQ - 如何更换熔丝 — RECOMMEND_APPROVE
- `68cc95bf-4243-425b-a94f-07e15841cce9` — LUNA2000 FAQ - How Often Do I Charge a Battery in Storage? — RECOMMEND_APPROVE
- `6ae25eec-2f61-453a-9b08-f4f1c31cb382` — LUNA2000 FAQ - 波特率协商 — RECOMMEND_APPROVE
- `6ae662ed-9382-4b96-95d7-acc7fb4d8250` — SUN2000 FAQ - Do PV inverters need to be grounded? — RECOMMEND_APPROVE
- `7be3e048-f732-41ff-b0fb-c14719a77e2c` — SUN2000 FAQ - 夜间WiFi通信不上 — RECOMMEND_APPROVE
- `7d691c02-8881-4308-acc4-f998befdd0fb` — SUN2000 FAQ - PV inverters are unable to power on. — RECOMMEND_APPROVE
- `836cc336-8af6-4d81-9f43-86a59e794a73` — LUNA2000 FAQ - Checking Cable Connection whe…to Be Upgraded — RECOMMEND_APPROVE
- `9cb20238-ef5f-4719-87db-94f57afba008` — SUN2000 FAQ - The WiFi communication fails at night. — RECOMMEND_APPROVE
- `9f9bf42c-4d14-4759-9d61-ac156cc5d476` — LUNA2000 FAQ - How Do I Replace a Fuse — RECOMMEND_APPROVE
- `ed7da861-c472-4bbe-8389-66d6fee05134` — SUN2000 FAQ - The indicator is red. — RECOMMEND_APPROVE
- `f5151eb5-30d8-478c-b1e8-845d9f922f15` — LUNA2000 FAQ - How Do I Replace a Fuse — RECOMMEND_APPROVE

## B. 必须逐份审核

- `43e6764a-9360-4eec-9138-a138d6d11781` — Learn More — REQUIRE_INDIVIDUAL_REVIEW
- `6868aee7-0abf-43ee-b4b6-1ca5e3395945` — 5.47 MB — REQUIRE_INDIVIDUAL_REVIEW
- `6e4f1075-250b-41fb-8543-1bd80f50355d` — Smart String Grid Forming ESS Model: LUNA2000-5015-2S — REQUIRE_INDIVIDUAL_REVIEW
- `90a65f4f-55d1-4f6b-8174-3d1db7640dcd` — Resumen de Garantías — REQUIRE_INDIVIDUAL_REVIEW
- `a02949e7-614c-444d-8d84-441769980926` — Learn More — REQUIRE_INDIVIDUAL_REVIEW
- `b2d7dc42-9c17-4a58-8282-60b47c290337` — USB-Adapter2000 User Manual — REQUIRE_INDIVIDUAL_REVIEW
- `e19f6438-994d-4fff-b7e8-46a2d61409ba` — SUN2000-20-40KTL-M3 Quick Guide — REQUIRE_INDIVIDUAL_REVIEW
- `edc89f1d-57fc-4cd6-9f90-330544a28851` — SmartACU Modelo: SmartACU2000D — REQUIRE_INDIVIDUAL_REVIEW
- `f01f024d-88fe-429a-bf9c-d0cd246f4dba` — Smart String Grid Forming ESS Model: LUNA2000-4472-2S — REQUIRE_INDIVIDUAL_REVIEW
- `06db6aff-907e-47bc-982f-58b4246054c2` — SUN2000 FAQ - What should I do if i forgot my WiFi password? — REQUIRE_INDIVIDUAL_REVIEW
- `0e4a73cd-69a4-46c6-b4e5-890e13faecd2` — LUNA2000 FAQ - SOC Change Description — REQUIRE_INDIVIDUAL_REVIEW
- `eafb9599-bfdc-4223-815d-845a848bc867` — LUNA2000 FAQ - Baud Rate Negotiation — REQUIRE_INDIVIDUAL_REVIEW
- `f86e0709-c34c-4a89-bc29-6de55e857e6f` — SUN2000 FAQ - The inverter yield is low. — REQUIRE_INDIVIDUAL_REVIEW
- `058ddd98-e3e8-44b5-a154-fb86923c3ff4` — SmartLogger FAQ - SmartLogger and SmartMGC Alarm Reference — REQUIRE_INDIVIDUAL_REVIEW
- `33f4bc65-2de4-4661-92a3-52d0a279dd8f` — SUN2000 FAQ - SUN2000-(5K-12K)-MAP0 Series User Manual — REQUIRE_INDIVIDUAL_REVIEW
- `c9210d01-e3d3-45a3-b1aa-2f5853afbb01` — SUN2000 FAQ - SUN2000-(3KTL-10KTL)-M1 User Manual — REQUIRE_INDIVIDUAL_REVIEW
- `da7ee239-a195-4345-94d1-48a54085bf2c` — SmartLogger FAQ - SmartLogger3000 User Manual — REQUIRE_INDIVIDUAL_REVIEW
- `f5a5ef4b-9232-49c6-81f4-0b8424b35977` — LUNA2000 FAQ - HUAWEI LUNA2000-(107-241) Ser…artLogger3000) — REQUIRE_INDIVIDUAL_REVIEW

## C. 当前不得批准

- `candidate:e8538fe2a5a8feca` — SUN2000 FAQ - 逆变器发电量低 — NEEDS_METADATA
- `candidate:bb8e4d4a87e6fe1e` — SUN2000 FAQ - 光伏逆变器是否需要接地 — NEEDS_METADATA
- `candidate:c1c02fafe10d92b7` — SUN2000 FAQ - 光伏逆变器标配直流、交流、通信、储能端子或WiFi天线丢失 — NEEDS_METADATA
- `candidate:308d33b3137ac122` — LUNA2000 FAQ - i. Questions Related to C&I E…on, and Layout — NEEDS_METADATA
- `candidate:c856ae42c17fc6eb` — LUNA2000 FAQ - i. Questions Related to C&I G…on, and Layout — NEEDS_METADATA

## SmartLogger 专项

- 文档：2；Chunk：642。
- 两份长文档均保持 `REQUIRE_INDIVIDUAL_REVIEW`，即使自动阈值通过也不得批量批准。
- 每份已使用文档 ID 派生的固定种子随机抽取 20 个不重复 Chunk，人工结果列保持空白。
- `058ddd98-e3e8-44b5-a154-fb86923c3ff4`：exact=16.67%，near=5.33%，locator=100.00%，表格样式 Chunk=26，重复页眉候选=47，阈值通过=False。
- `da7ee239-a195-4345-94d1-48a54085bf2c`：exact=3.86%，near=7.32%，locator=100.00%，表格样式 Chunk=12，重复页眉候选=19，阈值通过=False。

## FAQ 重复检查

- FAQ 候选：25；独立组：24；重复/近重复组：1；合并候选对：1。
- 仅生成 `applicable_device_models` 合并建议，没有修改文档或 Chunk。

## 告警人工抽样

- 显式告警：15；命名告警：20；排障步骤：20；安全动作：20。
- 所有 `review_result` 和 `notes` 均为空，等待人工核验。

## Benchmark 缺口

- 原 no-answer=4，补充=11。
- 原 hard-negative=8，补充=7。
- 新候选状态只为 `engineering_candidate`，expected IDs 均为空，expert_verified 写入为 0。

## 推荐人工审核顺序

第一批只批准以下 3 份代表性文档：

- `12703ebb-4860-4a8a-bed3-11734dbcdfa5` — LUNA2000 FAQ - 如何回收废旧电池 — RECOMMEND_APPROVE
- `2cc85307-e1f3-4382-896f-2cdae645af11` — SUN2000 FAQ - WiFi忘记密码 — RECOMMEND_APPROVE
- `2f6e8766-df74-4e31-abd4-c4b806a538bb` — SUN2000 FAQ - 光伏逆变器不开机 — RECOMMEND_APPROVE

随后运行：

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
uv run python scripts\check_task25b_r2_u3_corpus_gate.py --resume-after-document-approval
```

确认 active Chunk、状态过滤和引用正常后，再逐份处理两份 SmartLogger 长文档。达到 300 active Chunk 后先暂停扩充并复核门禁，不要求一次批准全部 34 份。

审核页面：http://127.0.0.1:8012/review

## 汇总

- 推荐批准：16。
- 必须逐份审核：18。
- NEEDS_METADATA：5。
- projected chunks：1161。
- exact duplicate chunks：145；near duplicate chunks：71。
- source locator/page coverage：100.00%；heading coverage：92.76%。

## R2 人工批准后复核（2026-07-12）

- R1 推荐的 3 份代表性 FAQ 已由真实 admin 人工批准，审计链完整。
- 复核同时发现 SUN2000、LUNA2000、SmartLogger3000 三份长篇手册曾被非预期批准；已通过审计化撤回 API 恢复为 `pending_review`，保留原批准事件并新增 before/after、操作人、原因和 OperationLog。
- 当前只剩指定 3 份 FAQ 为 approved，active formal Chunk=3；Corpus Gate 仍为 `CORPUS_BLOCKED`，Pilot 不允许。
- 两份 SmartLogger 当前解析版本均必须逐份审核、先重切分，不得进入 Pilot。
