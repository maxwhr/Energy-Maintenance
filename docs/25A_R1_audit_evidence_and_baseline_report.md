# Task 25A-R1 审计证据加固与重构基线冻结报告

生成时间：2026-07-10T13:51:23.944120+00:00

## 1. Executive Summary

Task 25A 关于代码规模、真实 PostgreSQL/Alembic、前后端构建、安全和业务回归边界的事实仍成立；原 83 项 maturity 因人工预写、浏览器未全量执行、性能样本/QPS 算法和依赖用途未拆分而不能继续作为可靠成熟度结论。R1 已建立来源、时间、环境、SHA、mock/real 和 current/historical 分离的证据注册表。
- 新需求统计：VERIFIED=24，IMPLEMENTED_BUT_NOT_FULLY_VERIFIED=36，PARTIAL=16，PLACEHOLDER_OR_MOCK=4，MISSING=3。
- 重构基线：可靠且已冻结；Git 疑似误删=0；unknown=0。
- Task 25G0：**GO**；Task 25B：**CONDITIONAL-GO**（不得在本任务内开始）。
- P0：LoongArch/Kylin 未做实机安装/启动/闭环；相似故障图片检索、检索准确率金标准和备份恢复仍缺失。P1：当前真实 provider 未复验，UI 美观/便捷和稳定性无充分量化证据。

## 2. Audit Method Correction

原 `requirement_rows()` 将 maturity 人工写入；R1 只保留 requirement_id/文本和适用门槛，最终状态由 evidence registry 自动计算。每项 evidence 记录来源、test_id、命令、时间、环境、current/historical、mock/real/fallback、业务/数据库/browser/performance/security 断言、artifact 和 SHA-256。历史 real-call 只证明曾实现；UI 必须有当前 browser；质量词必须有足够量化证据。

## 3. Requirement Status Changes

- old verified=35；new verified=24。
- old implemented=27；new implemented=36。
- downgraded=16；upgraded=4；unchanged=63。
- strength：STRONG=24；MODERATE=17；WEAK=40；NONE=2。

## 4. Git Worktree Classification

状态项=160；modified=27；deleted=52；untracked=81。52 个 deleted 全部逐项审计，其中旧哈希生成资产=52、替代/重命名=0、疑似误删=0、unknown=0。本任务恢复文件=0、删除文件=0。

## 5. Browser Acceptance

discovered=7；executed=7；passed=7；failed=0；blocked=0；skipped=0；console/page/network=0/0/0；viewer=PASSED；admin=PASSED。

## 6. Performance Baseline

R1 禁止默认账号/密码，使用安全测试配置；QPS 以真实 batch 墙钟计算；serial/concurrency 分开；warmup、并发错误、超时、HTTP 分布、响应大小、业务断言与写入计数全部记录。

| Endpoint | Serial p95 | Concurrent p95 | 分类 |
|---|---:|---:|---|
| `GET /api/health` | 28.491 | 42.045 | PASS |
| `POST /api/auth/login` | 283.973 | 220.495 | PASS |
| `GET /api/devices?page=1&page_size=20` | 36.949 | 153.239 | PASS |
| `GET /api/knowledge/documents?page=1&page_size=20` | 41.638 | 165.715 | PASS |
| `GET /api/kg/search?keyword=SUN2000&limit=20` | 48.807 | 203.356 | PASS |
| `POST /api/retrieval/query` | 140.451 | 410.129 | PASS |
| `POST /api/diagnosis/analyze` | 181.827 | 197.335 | PASS |
| `GET /api/sop/templates?page=1&page_size=20` | 47.158 | 322.135 | PASS |
| `GET /api/maintenance/tasks?page=1&page_size=20` | 65.133 | 311.497 | PASS |
| `GET /api/record-center/search?record_type=all&page=1&page_size=20` | 1382.942 | 11635.603 | NEEDS_OPTIMIZATION |
| `GET /api/kg/business-context?manufacturer=huawei&product_series=SUN2000&question=low%20insulation&limit=20` | 246.774 | 1911.709 | NEEDS_OPTIMIZATION |
| `GET /api/agents/runs?page=1&page_size=20` | 37.367 | 451.643 | PASS |
| `GET /api/system/status` | 38.07 | 158.796 | PASS |

总体=NEEDS_OPTIMIZATION；error_rate=0.0；timeout_rate=0.0。Record Center serial p50/p95/p99=1114.014/1382.942/1467.615 ms。

## 7. Code Candidate Review

dead/duplicate/deprecated 共 111；`safe_to_remove_now=true`=0；本任务删除=0。所有候选留待 Task 25E 带动态注册、路由、兼容性和回归证据复核。

## 8. LoongArch Dependency Classification

用途统计：{"RUNTIME_REQUIRED": 6, "RUNTIME_OPTIONAL": 6, "DEVELOPMENT_ONLY": 1, "BUILD_TIME_ONLY": 3, "TEST_ONLY": 2}。高风险 runtime=pydantic-core, greenlet, psycopg, libpq。Node/Vite/Rolldown 可在非龙芯构建机预构建；Playwright/Chromium 为测试依赖；实机状态=NOT_EXECUTED。

## 9. Baseline Manifest

Manifest=`.runtime/task25a_r1/baseline_manifest.json`；HEAD=`53145339c66b6efed489156ea68cf55d24161ab8`；backend hash=`7463434aecb8fde236189a68cca30796022c435a90463891d8ec674061948b8b`；frontend hash=`d0cc70d67073d34fe662405f6d802e0db10c106f5ca37ac1910758d8eefdbb5e`；migration hash=`efbd7453f11a77163c143a86ea2ee68674b1bfdb2da05aace415043511ba1cdd`；OpenAPI paths=150；DB tables=42。

## 10. Current Competition Readiness

B/S 与 PC Web、结构化知识/诊断/SOP/任务/追溯具备当前功能证据；OCR/视觉理解只有历史 real 与当前 mock/blocked 边界；确定性向量不是语义检索；相似图检索缺失；反馈回流仅记录未闭环；LoongArch/Kylin 仅静态分类。

## 11. P0 Issues

- LoongArch + Kylin 实机依赖安装、服务启动、PostgreSQL、解析和闭环未验证。
- R-MM-08 相似故障图片检索缺失；R-RAG-11 无金标准准确率；R-NFR-08 无当前恢复演练证据。

## 12. P1 Issues

- 真实 Cloud/MIMO/OCR provider 本轮按约束未调用，历史可用性不能视为当前可用。
- UI 美观/交互便捷、稳定性、容量与可观测性缺少充分量化或长稳证据。
- Record Center 需在 Task 25E 用生产规模夹具与 EXPLAIN ANALYZE 复核。

## 13. P2 Issues

- lint package script 缺失时保持 SKIPPED，不伪报 passed。
- 静态生成资产哈希替换使工作树噪声较大，后续 staging 必须逐项确认。

## 14. Go / No-Go Decision

- Task 25G0：**GO**。条件：只做目标机依赖/import/服务探针，不将静态分类当实机通过。
- Task 25B：**CONDITIONAL-GO**。条件：先完成/评审 G0 风险与 R1 P0/P1 处置计划；本轮未开始 Task 25B。

## 15. No-package Confirmation

- 新 delivery zip=false；delivery Git 状态=clean；delivery_staging 未由本任务更新；Compress-Archive=false；docs.zip modified=false。

## 16. Git Confirmation

- git add=false；git commit=false；reset/clean/restore=false；staged_file_count=0。现有用户改动全部保留；本任务没有恢复或删除文件。

R1 acceptance result：**PASSED**。未通过/缺失的关键测试：无。

## Task 25B Delta

Task 25B pre-task drift classification was `NO_DRIFT` against this baseline. It intentionally adds migration 0009, backend/frontend source, static frontend and Task 25B reports. All prior key security/RBAC/RAG/agent/conversion regressions were rerun and passed. Record Center and KG business context remain `NEEDS_OPTIMIZATION` in the performance baseline; this task does not claim to fix those P1 items.
