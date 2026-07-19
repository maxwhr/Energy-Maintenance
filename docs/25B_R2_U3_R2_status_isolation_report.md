# Task 25B-R2-U3-R2 状态隔离复核

生成时间：`2026-07-12T05:49:28.147985+00:00`

## 结论

- 结果：**PASSED**。
- 3/3 已批准 FAQ 可通过 PostgreSQL 正式关键词候选查询召回，且 reference 可回查 Chunk/Document、source URL 与 locator。
- pending、NEEDS_METADATA、marketing-only、archived、rejected 泄漏均为 0。
- `pilot_r2` active vectors：0；未调用真实 Embedding 或 DashVector。
- 默认 Partition 数据库映射快照：count 0 → 0，SHA-256 未变化=true。

## Task25BR2U3R2_ 查询

- `Task25BR2U3R2_回收废旧电池`：目标 `12703ebb-4860-4a8a-bed3-11734dbcdfa5` 召回，reference=1，结果=通过。
- `Task25BR2U3R2_WiFi忘记密码`：目标 `2cc85307-e1f3-4382-896f-2cdae645af11` 召回，reference=1，结果=通过。
- `Task25BR2U3R2_光伏逆变器不开机`：目标 `2f6e8766-df74-4e31-abd4-c4b806a538bb` 召回，reference=1，结果=通过。

## 隔离统计

- pending searchable：0。
- NEEDS_METADATA searchable：0。
- marketing searchable：0。
- archived searchable：0。
- rejected searchable：0。

验证使用本地 SQLAlchemy/PostgreSQL 检索仓储，`external_api_called=false`。
