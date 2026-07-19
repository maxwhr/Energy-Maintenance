# Task 25B-R2-U3 Benchmark 人工审核报告

## 候选池

- U2+U3 定向候选：200；全部为 `engineering_verified`。
- expert_verified：0；second reviewed：0。
- vector-heavy：52；no-answer：4；hard negatives：8。
- 自动 expert verification：0。
- 数据库全局历史候选为 640；不得将全局数误写为 U2+U3 专项候选数。

## 页面与门禁

地址：http://127.0.0.1:8012/system/retrieval-quality

页面支持 A（接受）、M（需修改）、X（拒绝）、N（下一条），展示 expected document/chunk、页码、原文片段、类别、状态、before/after 与第二审核状态。第二审核必须使用不同 expert/admin 账户。

Benchmark 审核尚未开始。只有文档批准且 active formal Chunk 达到 300 后，才进入 `AWAITING_HUMAN_BENCHMARK_REVIEW`；当前不得冻结或执行 official Pilot Test/Blind Test。

