# Energy-Maintenance

Energy-Maintenance is a PostgreSQL-backed foundation project for renewable energy equipment inspection and maintenance assistance. It focuses on photovoltaic, storage, and power equipment scenarios, including knowledge base metadata, retrieval-style QA, fault diagnosis, maintenance tasks, QA records, devices, basic users, and system status.

## Technology Stack

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic.
- Database: PostgreSQL with `psycopg`.
- Frontend: Vue 3, Vite, TypeScript, Vue Router, Pinia, Axios, Element Plus.
- Deployment target: native LoongArch + Kylin deployment.
- Docker is not used.

## Backend Startup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger:

```text
http://localhost:8000/docs
```

## Frontend Startup

```bash
cd frontend
npm install
npm run dev
```

Default URL:

```text
http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`.

## PostgreSQL Initialization

Create the PostgreSQL database and user manually:

Windows with `psql` in PATH:

```powershell
psql -U postgres -c "CREATE USER energy_user WITH PASSWORD 'energy_password';"
psql -U postgres -c "CREATE DATABASE energy_maintenance OWNER energy_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;"
```

Linux:

```bash
sudo -u postgres psql -c "CREATE USER energy_user WITH PASSWORD 'energy_password';"
sudo -u postgres psql -c "CREATE DATABASE energy_maintenance OWNER energy_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;"
```

Equivalent SQL:

```sql
CREATE USER energy_user WITH PASSWORD 'energy_password';
CREATE DATABASE energy_maintenance OWNER energy_user;
GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;
```

Then configure `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@localhost:5432/energy_maintenance
```

Run migrations:

```bash
cd backend
alembic upgrade head
```

Quick upload check after backend startup:

```bash
curl -X POST http://localhost:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_photovoltaic_maintenance.txt" \
  -F "document_type=manual" \
  -F "device_type=inverter" \
  -F "source=local_sample"
```

Knowledge upload settings in `backend/.env`:

```env
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_DOCUMENT_EXTENSIONS=txt,md,pdf,docx
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=150
```

## Current API Paths

- `GET /api/health`
- `GET /api/system/info`
- `GET /api/system/status`
- `GET /api/system/statistics`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{user_id}`
- `POST /api/users/{user_id}/enable`
- `POST /api/users/{user_id}/disable`
- `GET /api/devices`
- `POST /api/devices`
- `GET /api/devices/statistics/summary`
- `GET /api/devices/{device_id}`
- `PUT /api/devices/{device_id}`
- `POST /api/devices/{device_id}/retire`
- `GET /api/devices/{device_id}/maintenance-records`
- `POST /api/devices/{device_id}/maintenance-records`
- `GET /api/knowledge/documents`
- `POST /api/knowledge/documents/upload`
- `GET /api/knowledge/documents/{document_id}`
- `GET /api/knowledge/documents/{document_id}/chunks`
- `DELETE /api/knowledge/documents/{document_id}`
- `POST /api/knowledge/documents/{document_id}/reparse`
- `GET /api/knowledge/contributions`
- `POST /api/knowledge/contributions`
- `GET /api/knowledge/contributions/{contribution_id}`
- `PUT /api/knowledge/contributions/{contribution_id}`
- `POST /api/knowledge/contributions/{contribution_id}/submit`
- `POST /api/knowledge/contributions/{contribution_id}/approve`
- `POST /api/knowledge/contributions/{contribution_id}/reject`
- `POST /api/knowledge/contributions/{contribution_id}/request-changes`
- `POST /api/knowledge/contributions/{contribution_id}/convert-to-document`
- `POST /api/knowledge/contributions/{contribution_id}/archive`
- `GET /api/review/knowledge`
- `GET /api/review/knowledge/{document_id}`
- `POST /api/review/knowledge/{document_id}/approve`
- `POST /api/review/knowledge/{document_id}/reject`
- `POST /api/review/knowledge/{document_id}/archive`
- `POST /api/retrieval/query`
- `GET /api/retrieval/records`
- `GET /api/retrieval/records/{trace_id}`
- `POST /api/diagnosis/analyze`
- `GET /api/diagnosis/records`
- `GET /api/diagnosis/records/{trace_id}`
- `GET /api/maintenance/tasks`
- `POST /api/maintenance/tasks`
- `GET /api/maintenance/tasks/statistics/summary`
- `GET /api/maintenance/tasks/assignable-users`
- `GET /api/maintenance/tasks/{task_id}`
- `PUT /api/maintenance/tasks/{task_id}`
- `POST /api/maintenance/tasks/{task_id}/assign`
- `POST /api/maintenance/tasks/{task_id}/start`
- `POST /api/maintenance/tasks/{task_id}/complete`
- `POST /api/maintenance/tasks/{task_id}/cancel`
- `GET /api/media`
- `POST /api/media/upload`
- `GET /api/media/ocr/status`
- `GET /api/media/{media_id}`
- `GET /api/media/{media_id}/content`
- `GET /api/media/{media_id}/ocr`
- `POST /api/media/{media_id}/ocr`
- `GET /api/sop/templates`
- `POST /api/sop/templates`
- `GET /api/sop/templates/{template_id}`
- `PUT /api/sop/templates/{template_id}`
- `POST /api/sop/templates/{template_id}/archive`
- `POST /api/sop/generate`
- `GET /api/sop/executions`
- `POST /api/sop/executions`
- `PUT /api/sop/executions/{execution_id}`
- `GET /api/record-center/overview`
- `GET /api/record-center/search`
- `GET /api/record-center/records/{record_type}/{record_id}`
- `GET /api/record-center/devices/{device_id}/timeline`
- `GET /api/model-gateway/status`
- `POST /api/model-gateway/test`
- `POST /api/model-gateway/chat`
- `GET /api/model-gateway/logs`
- `GET /api/model-gateway/logs/{log_id}`
- `GET /api/kg/overview`
- `GET /api/kg/graph`
- `GET /api/kg/search`
- `GET /api/kg/business-context`
- `GET /api/kg/nodes`
- `POST /api/kg/nodes`
- `PUT /api/kg/nodes/{node_id}`
- `POST /api/kg/nodes/{node_id}/archive`
- `GET /api/kg/edges`
- `POST /api/kg/edges`
- `PUT /api/kg/edges/{edge_id}`
- `POST /api/kg/edges/{edge_id}/archive`
- `GET /api/kg/evidence`
- `GET /api/kg/neighborhood/{node_id}`
- `GET /api/kg/path`
- `GET /api/kg/extraction-runs`
- `GET /api/kg/candidates`
- `POST /api/kg/candidates/{candidate_id}/approve`
- `POST /api/kg/candidates/{candidate_id}/reject`
- `POST /api/kg/extract/from-document/{document_id}`
- `POST /api/kg/extract/from-contribution/{contribution_id}`
- `POST /api/kg/extract/from-record/{record_type}/{record_id}`
- `GET /api/corrections`
- `POST /api/corrections`
- `GET /api/corrections/{correction_id}`
- `POST /api/corrections/{correction_id}/resolve`

## Completed

- FastAPI application startup.
- CORS configuration.
- Unified API router under `/api`.
- Unified response shape.
- Basic exception handling.
- SQLAlchemy models for `users`, `devices`, `knowledge_documents`, `knowledge_chunks`, `maintenance_tasks`, `diagnosis_records`, and `qa_records`.
- Alembic environment, initial migration, and phase-two persistence migration.
- PostgreSQL-backed repositories for knowledge documents, knowledge chunks, maintenance tasks, QA records, diagnosis records, devices, and basic users.
- Knowledge file upload, text extraction, cleaning, chunking, and chunk persistence for `txt`, `md`, `pdf`, and `docx`.
- Vue 3 frontend shell with industrial maintenance platform layout.
- Pages for login, dashboard, system status, knowledge base, retrieval QA, fault diagnosis, and maintenance tasks.
- Axios API calls aligned with the backend API paths.

## PostgreSQL Persistence in This Phase

The following modules now use PostgreSQL persistence:

- Knowledge document list, detail, creation.
- Knowledge document upload and parsing result.
- Knowledge chunk list and creation by document.
- Maintenance task list, detail, creation, and status update.
- QA record persistence and listing.
- Diagnosis record persistence and listing.
- Device and basic user repositories.

## Simulated Logic Still Present

The following modules still use rule-based placeholder logic, but their records are saved to PostgreSQL:

- Retrieval query answer generation.
- Fault diagnosis result generation.
- PDF parsing supports text-based PDFs only; scanned PDFs still require future OCR.

## Next Work

The next stage should add retrieval over persisted chunks, Safety-Gate rule persistence, document review/publish workflow, and richer device/task management pages.
## Task 24B DashVector Note

The current vector RAG enhancement route is DashVector metadata + hybrid retrieval. PostgreSQL remains the source of truth; DashVector is the future online vector recall service. Local tests use `fake_in_memory` and `deterministic_test` only. Real DashVector and real embedding APIs are not called by default and require explicit online acceptance.

## Task 24D Security Hardening Note

Task 24D adds production security checks, CORS configuration from settings, JSON/upload request size limits, lightweight in-memory rate limiting, secret-leak scanning, log sanitization, upload/path traversal checks, and an RBAC matrix script.

The backend exposes only sanitized security status through `/api/system/status`; API keys, Authorization headers, tokens, passwords, local paths, and base64 payloads must not appear in responses or logs. Real DashVector, MIMO, OCR, Cloud LLM, and embedding calls remain opt-in and blocked unless explicitly configured and re-tested. Any previously exposed real keys must be rotated before production use.

## Task 24C Real External API Acceptance Note

Task 24C completed controlled real-call acceptance for the configured Cloud LLM, MIMO/Vision, and OCR API providers. The unified acceptance result was `passed=3`, `blocked=2`, `failed=0`: Cloud LLM, MIMO/Vision, and OCR API passed; DashVector and Embedding remained blocked because the real vector and embedding configuration was incomplete.

Real-call execution is explicit only. Dry-run/mock-run results must not be presented as real provider success, and blocked providers must not be documented as passed. Real provider outputs are stored as sanitized logs or auxiliary media evidence and still require human review before maintenance decisions.

## Task 25B High-Precision Multimodal RAG

Task 25B adds real DashScope `text-embedding-v4` (1024 dimensions), real DashVector versioned indexes, semantic document chunks, query understanding, RRF/feature-fusion reranking, citation validation, retrieval evaluation, and descriptor-based cross-modal retrieval.

Current result is `PARTIAL / QUALITY_GATE_FAILED`: real Embedding, real DashVector, controlled test-only indexing, and multimodal manual/case/similar-media checks passed, but hybrid_rerank Recall@10, MRR, nDCG@10, and p95 did not meet the required thresholds. PostgreSQL remains the source of truth; full reindex is disabled; no raw image embedding is used. See `docs/25B_high_precision_multimodal_rag_report.md`.

<!-- TASK25B_R1_BEGIN -->
## Task 25B-R1 controlled blind acceptance (2026-07-11T02:32:50.109583+00:00)

- test_v1 is exposed and regression-only; test_v2 is independently frozen with SHA-256 `2cdf413a1ca58fc77ea3ca64f117f1b909c6bd2ab8ca556ca2fd2bba25bfbe5b`.
- Corpus: 24 documents, 192 active chunks, 48 hard negatives.
- Adaptive blind metrics: R@5=1.000000, R@10=1.000000, MRR=0.981481, nDCG@10=0.986331, warm p95=704.712 ms.
- Reranker disabled: no measurable dev gain. Default retrieval strategy remains keyword.
- Canary uses an isolated partition because the provider collection quota is exhausted; v1 default partitions remain intact.
- Formal full reindex, package generation and Git commit were not executed. LoongArch real-machine testing remains outstanding.
<!-- TASK25B_R1_END -->


<!-- TASK25B_R2_BEGIN -->
## Task 25B-R2 正式知识 Pilot 状态

- 状态：`BLOCKED_CONFIG`；正式可用语料只有 6 份文档、11 个 active Chunk，未达到 300。
- 独立 Pilot Collection `energy_kn_te_v4_1024_pilot1` 创建被服务商 2 个 Collection 配额阻断；未删除或复用现有 Collection。
- 已生成 150 条 `draft` 候选；`expert_verified=0`，未冻结或运行 `official_pilot_test_v1`。
- 默认 Collection 与 `keyword` 策略未改变；`TASK25B_ALLOW_FULL_REINDEX=false`，全量重建决策为 NO-GO。
- 本任务未打包、未提交 Git；LoongArch/Kylin 仍未实机验收。
<!-- TASK25B_R2_END -->

## Task 25B-R2-U3 当前状态

官方检修候选已扩充到 34 份 pending 文档、1,161 个预计 Chunk，审核入口为 `http://127.0.0.1:8012/review`。状态为 `AWAITING_HUMAN_DOCUMENT_APPROVAL`：尚无 approved/active formal Chunk，尚未执行 Pilot 索引或正式全量重建。详见 `docs/25B_R2_U3_official_corpus_expansion_report.md` 与 `docs/25B_R2_U3_pilot_resume_report.md`。

<!-- TASK25B_R3_DEV_BEGIN -->
## Task 25B-R2-U3-R3-DEV 中文工程 Pilot 更新

- 中文 Corpus Gate：`CHINESE_CORPUS_GATE_PASSED`，16 份文档、1262 个当前 Chunk。
- 开发工程审批与真实专家审批严格分离；`expert_verified=false`。
- 英文保留但不进入默认检索或 `pilot_r2`。
- Pilot 索引：1262 upserted；恢复阶段未重复索引，正式全量重建未执行。
- 质量门原 run 已完整产生 600/600 条结果；最终判定 `DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- 中断来自 Codex 模型容量，不是项目服务故障；恢复时未重复工程审批。
<!-- TASK25B_R3_DEV_END -->

<!-- TASK25B_R3_DEV_R1_BEGIN -->
## Task 25B-R3-DEV-R1 检索治理更新

- v1 run `f1941ec2-9878-45a1-b554-8d9f2f2ec911` 失败且保留；v2 run `3e40e25f-f1f1-4146-9e1e-629d2ce76045` 独立保存。
- Benchmark 数据集状态：`BENCHMARK_DATASET_READY`；质量门状态：`QUALITY_GATE_FAILED`，二者不得混淆。
- Scope：`chinese_engineering_pilot_r2`；Canary：`CANARY_PASSED`；正式 v2：`DEVELOPMENT_ENGINEERING_QUALITY_GATE_FAILED`。
- Pilot 对账：1262/1262，re-embedded=0、re-upserted=0。
- 工程审批不等于专家验证；正式全量重建未执行；不打包、不提交 Git。
<!-- TASK25B_R3_DEV_R1_END -->

<!-- Task25B-R3-DEV-R2 -->

Task 25B-R3-DEV-R2 adds result-set refinement and a metric contract for Chinese Pilot retrieval. The current v3 Canary failed, so vector semantic superiority is not claimed.

<!-- TASK25B_R3_DEV_R3 -->
## Task 25B-R3-DEV-R3 semantic recall diagnosis

- R2 Canary remains `CANARY_FAILED` and its artifacts are preserved read-only.
- Raw Chunk representation dilution was diagnosed with train/dev-only embedding pairs; DashVector filtering and mapping were not the root cause.
- An isolated `pilot_r3_semantic` A/B partition was created with 416 source-only anchors. `pilot_r2`, the default partition, and the original 1,262 vectors were not changed.
- The independent Canary failed: semantic Candidate Recall@50 = 0.444444, below 0.90. `test_v3_1` was not created or frozen and no formal quality run or full reindex occurred.
- `expert_verified=false`; no package, Git commit, or LoongArch physical verification occurred.
# Task 25B-R3-DEV-R4 engineering status

The isolated R4 experiment builds source-grounded maintenance semantic units and typed anchors in `pilot_r4_grounded`. It does not replace the default retrieval route, rewrite `pilot_r2`/`pilot_r3_semantic`, re-embed the original 1,262 chunk vectors, approve documents, or authorize a full reindex. Current aggregate evidence is available to authenticated users at `GET /api/retrieval/scope/r4-status` and in the read-only retrieval quality panel. Formal v4 creation and execution are guarded by the Grounded Canary result.
