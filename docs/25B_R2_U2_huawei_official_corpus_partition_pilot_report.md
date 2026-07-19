# Task 25B-R2-U2 华为官方语料与 Partition Pilot 报告

## 执行结论

状态：`PARTIAL / BLOCKED_HUMAN_REVIEW`。

官方语料发现、匿名下载、来源治理、质量筛选、pending 导入、审核 UI、现有 DashVector Collection 的 `pilot_r2` Partition 能力验证、查询路由和回滚演练均已完成。由于任务明确禁止自动批准，当前 9 份文档仍为 `pending_review`，`approved_for_pilot=0`；因此 Pilot 索引被正确阻断，未写入任何正式或 Pilot 向量。

## 1. Huawei Official Discovery

- pages scanned: 20
- official documents found: 37
- downloadable: 25
- login required: 2
- manual download required: 12
- unsupported third-party skipped: 80
- access control bypassed: false
- crawl depth limit: 4
- request delay: 1 second

匿名请求遇到登录、403 或需人工下载的资料即停止该文档，没有使用 Cookie、Token、Authorization 或绕过手段。发现入口包括华为智能光伏下载中心与产品支持页；下载最终域名仅允许华为官方域名和官方 CDN。

## 2. Download and Provenance

- downloaded: 25
- PDF: 25
- DOCX: 0
- duplicate SHA-256: 0
- failed: 0
- total size: 44,631,935 bytes (42.56 MiB)
- SHA-256 completeness: 25/25
- redistribution authorized: false

下载文件位于被 Git 忽略的 `backend/storage/formal_corpus_inbox/huawei_official/`。manifest 保留 `VENDOR_OFFICIAL`、Huawei、issuer、`vendor_public`、source/final URL、下载时间、SHA-256、版本、语言、产品族、型号和文档类型。`vendor_public` 仅表示公开可下载，不代表可重新分发。

## 3. Products and Quality

37 条发现记录中的关键词覆盖（类别可重叠）：

- SUN2000: 17
- LUNA2000: 21
- MERC: 3
- SmartGuard: 0
- SmartLogger / management: 3
- FusionSolar: 0

发现文档类型：USER_MANUAL 1、QUICK_GUIDE 3、TECHNICAL_DOCUMENT 29、DATASHEET 4。

25 个已下载文件的质量判定：

- READY_FOR_DRAFT_IMPORT: 9
- MARKETING_ONLY: 16
- REQUIRES_OCR: 0
- REQUIRES_MANUAL_REVIEW: 0
- INVALID_FILE: 0
- pages: 65
- model codes: 103
- alarm codes: 0
- safety sections: 13

16 份营销/参数型材料未进入正式检修知识 Chunk 门槛。

## 4. Knowledge Import and Review

- pending documents created: 9
- parsed: 9
- chunks: 84
- chunks with content hash: 84/84
- vendor source verified: 9
- content parse verified: 9
- approved for pilot: 0
- automatically approved: 0
- formal vector records created: 0
- formal KG nodes created: 0

导入完整性检查通过：9 个 `file_sha256 + source_url` 复合幂等键均唯一，没有重复知识文档。审核页面新增华为官方标识、原始链接、型号、文档类型/版本/语言/发布日期、SHA-256、页数、Chunk 数、质量、OCR 和重复状态；expert/admin 可单条或按同 issuer、同产品族批量批准，批准写审计日志。工程脚本只设置来源与解析验证，不设置 `approved_for_pilot`。

## 5. DashVector Existing Cluster Partition

- existing Cluster: true
- existing Collection: `energy_kn_te_v4_1024_v1`
- dimension: 1024
- metric: cosine
- dtype: float
- new Cluster: false
- new Collection: false
- pilot Partition: `pilot_r2`（已创建并可 describe）
- partition self-query: passed
- default Partition isolation: passed
- probe vector deleted: true
- Collection deleted: false
- Partition deleted: false

Pilot 索引脚本只接受 `vendor_official + approved + parsed + active + approved_for_pilot=true`，并固定写入现有 Collection 的 `pilot_r2`。当前无人工批准文档，结果为 `BLOCKED_HUMAN_REVIEW`，indexed=0；默认 Partition、Media Collection 均未写入，全量重建未执行。

## 6. Pilot Query, Rollback and Benchmark

Pilot Session 使用现有 Collection 和 `pilot_r2` namespace；普通请求不指定 Partition。受控验收进程临时打开本进程 Pilot/rollback 门禁，创建未激活会话后立即回滚，确认默认路由恢复、审计事件写入，且不删除文档或 Partition、不修改 `.env`。

从 9 份官方资料、84 个 Chunk 生成 150 条 benchmark 候选，覆盖 15 类查询，含预期文档、Chunk、页码/章节与原文片段。机器状态为 `engineering_verified`，自动 `expert_verified` 为 0，仍需人工专家复核与二审。

## 7. Regression Evidence

- `python -m compileall -q app scripts tests`: passed
- `alembic -c alembic.ini current`: `20260601_0010 (head)`
- `alembic -c alembic.ini upgrade head`: passed against PostgreSQL
- `python -m pytest -q`: 48 passed, 2 deprecation warnings
- secret leak scan: passed_with_notes, 0 blocking; key values not printed
- npm audit: 0 vulnerabilities
- `npm run build`: passed, 1,968 modules transformed
- browser: passed; 9 pending official cards rendered; viewer approval 403; no console/network errors
- final smoke: passed; health/login/review/Pilot status all 200
- `.env` SHA-256 unchanged from baseline
- temporary 8012 server stopped; pre-existing 8010 listener preserved

## 8. Runtime Evidence

Evidence is stored under `.runtime/task25b_r2_u2/`, including discovery JSON/CSV, manual-download queue, download manifest/failures, corpus quality, import result/integrity, partition capability, Pilot indexing/reconciliation, rollback, benchmark, browser and final smoke reports. Runtime evidence and downloaded vendor files are not delivery packages and are not committed.

## 9. Known Issues and Resume Decision

- 12 discovered documents remain manual-download/blocked-access candidates; access controls were not bypassed.
- No SmartGuard or FusionSolar-specific document was captured in this bounded 20-page run.
- The formal-ready set contains no extracted alarm codes and only 84 chunks; coverage is insufficient for the previous R2 minimum of 300 Pilot chunks.
- The explicit U2 product range includes LUNA/MERC/management products beyond the repository's original first-version inverter-only taxonomy. They remain represented through `product_family` and `device_models` metadata while the core compatibility field stays `pv_inverter`; this taxonomy bridge needs a later scope decision before formal release.
- Human work remaining: approve/reject 9 documents, expert-review benchmark candidates, provide second reviews, and expand formal maintenance/alarm corpus.

Decision: Huawei corpus ingestion pipeline is ready and the current batch is ready for human review. Pilot indexing and resuming the Task 25B-R2 official evaluation are not ready until human approval and corpus/benchmark thresholds are met.

## 10. U3 Continuation Addendum

U3 added 25 pending official HTML/support documents and 1,077 candidate chunks. The combined U2+U3 review pool is now 34 documents and 1,161 projected chunks, but approved/active remains 0 until real expert/admin review. The current pause is `AWAITING_HUMAN_DOCUMENT_APPROVAL`; no Pilot vector was created.
