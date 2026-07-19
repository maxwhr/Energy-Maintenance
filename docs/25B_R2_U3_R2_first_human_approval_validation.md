# Task 25B-R2-U3-R2 首批人工批准真实性验证

生成时间：`2026-07-12T05:49:26.374312+00:00`

## 结论

- 结果：**PASSED**。
- 用户指定 3 份 FAQ 均由真实 admin/expert 账号通过已认证审核 API 批准；审计事件、before/after、审核时间均存在。
- 未发现自动批准，未调用批量批准 API；本脚本只读验证。
- 当前非预期 approved 官方文档为 0。此前检测出的 3 份长篇手册已通过新建的审计化撤回 API 退回，不是直接数据库修改。

## 指定文档

- `12703ebb-4860-4a8a-bed3-11734dbcdfa5`：approved，审核人 `System Administrator`（admin），时间 `2026-07-12T12:51:07.779316+08:00`，审计事件 `1f78f10f-2154-4048-b241-b2ec02291c45`，active Chunk=1，locator/hash 覆盖率=100%/100%。
- `2cc85307-e1f3-4382-896f-2cdae645af11`：approved，审核人 `System Administrator`（admin），时间 `2026-07-12T12:51:26.246402+08:00`，审计事件 `7ed9d43a-ae16-4de3-ba6d-e2b3c481e846`，active Chunk=1，locator/hash 覆盖率=100%/100%。
- `2f6e8766-df74-4e31-abd4-c4b806a538bb`：approved，审核人 `System Administrator`（admin），时间 `2026-07-12T12:50:36.592745+08:00`，审计事件 `eefeecb3-373a-400e-b0aa-5560175d79de`，active Chunk=1，locator/hash 覆盖率=100%/100%。

## 非预期批准处置

- `f5a5ef4b-9232-49c6-81f4-0b8424b35977`：`approved` → `pending_review`，必须逐份审核。
- `c9210d01-e3d3-45a3-b1aa-2f5853afbb01`：`approved` → `pending_review`，必须逐份审核。
- `da7ee239-a195-4345-94d1-48a54085bf2c`：`approved` → `pending_review`，必须逐份审核。

每次撤回均保留原批准事件，并新增 `withdraw_approval` 记录与 OperationLog，包含 before/after、操作人、原因与 `automatic_operation=false`。SmartLogger 明确设置 `pilot_index_excluded=true`。

## 状态边界

- 其余 pending 官方文档：31。
- pending 文档进入正式 active corpus 的 Chunk：0。
- 文档 Chunk 行自身可保持 `active`，但只有父文档 `review_status=approved` 才具备正式检索资格。
