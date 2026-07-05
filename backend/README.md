# Energy-Maintenance Backend

FastAPI backend for Energy-Maintenance.

Current scope:

- `GET /api/health`
- `GET /api/system/info`
- `GET /api/system/status`
- SQLAlchemy database models and PostgreSQL persistence for the first-version core schema
- Alembic migration chain through `20260601_0003`
- document parsing, approved-only keyword retrieval, diagnosis, SOP, task, record-center, and media evidence APIs
- PostgreSQL-backed knowledge graph APIs and graph-enhanced retrieval, diagnosis, SOP, and record-center traceability

Media upload and business-context association are implemented for `jpg`, `jpeg`, `png`, and `webp`. OCR and image understanding are not enabled by default; image metadata and manual descriptions may be used, but unparsed image content must not be inferred.

Formal database configuration uses PostgreSQL. SQLite is not a formal database for this project.

Production initialization must set a strong `SECRET_KEY` and `ADMIN_PASSWORD`. `scripts/create_admin_user.py` only permits the local development password without `ADMIN_PASSWORD` outside production and prints a warning; it fails when `APP_ENV=production` or `ENV=production` and `ADMIN_PASSWORD` is missing.
---

## Task 02A Backend Boundary Update

The backend remains a FastAPI + SQLAlchemy 2.x + Alembic + PostgreSQL service for Energy-Maintenance.

### First-version Backend Focus

- Huawei and Sungrow PV inverter maintenance.
- PostgreSQL structured data and source-traceable records.
- Knowledge document metadata, chunks, QA records, diagnosis records, maintenance tasks.
- Future Model Gateway abstraction for llama.cpp + GGUF local model route and OpenAI-compatible cloud route.

### Current Static Review Notes

Task 02A does not modify backend models, schemas, migrations, repositories, services, or API handlers. It only documents the required alignment for the next database implementation task.

Real migration verification must be executed in a PostgreSQL environment:

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

SQLite is not a formal database for this backend. Docker is not the formal deployment route.
---

## Task 02B Schema Enhancement Update

Task 02B adds the database model and migration foundation for the expanded first-version scope.

### Added Tables

- `uploaded_media`
- `device_maintenance_records`
- `knowledge_contributions`
- `knowledge_review_records`
- `model_output_corrections`
- `sop_templates`
- `sop_execution_records`

### Enhanced Existing Tables

- `users`
- `devices`
- `knowledge_documents`
- `knowledge_chunks`
- `qa_records`
- `diagnosis_records`
- `maintenance_tasks`
- `model_call_logs`

### Migration

```bash
cd backend
uv run alembic -c alembic.ini upgrade head
```

The command above was intentionally not executed in Task 02B because this task only performs static model, schema, and migration preparation. Run it in the next real PostgreSQL verification task.

---

## Task 18D Knowledge Graph Business Integration

Task 18D connects the existing PostgreSQL knowledge graph to first-version business flows without adding a new migration or external graph database.

### Enhanced API Behavior

- `GET /api/kg/graph` returns active graph nodes and edges for lightweight visualization.
- `GET /api/kg/search` searches active graph nodes and edges.
- `GET /api/kg/business-context` returns active graph context grouped for retrieval, diagnosis, and SOP usage.
- `POST /api/retrieval/query` accepts `enable_kg_enhancement` and returns graph context, evidence, nodes, edges, and paths when relevant active graph data exists.
- `POST /api/diagnosis/analyze` accepts `enable_kg_enhancement` and returns graph-related causes, inspection items, actions, safety risks, and evidence.
- `POST /api/sop/generate` accepts `enable_kg_enhancement` and returns graph-related tools, parts, safety risks, SOP steps, and evidence.
- Record-center detail responses expose saved graph context and evidence summaries when available.

### Boundaries

- The graph source of truth remains PostgreSQL tables added by migration `20260601_0003`.
- Only active graph nodes, active graph edges, and real evidence links are used for business enhancement.
- Neo4j, NebulaGraph, JanusGraph, Elasticsearch, pgvector, embedding, OCR, and real model-based graph extraction are not introduced.
- `alembic current` should remain `20260601_0003 (head)`.

### Verification

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
uv run python scripts/seed_demo_knowledge_graph.py
uv run python scripts/check_knowledge_graph_flow.py
uv run python scripts/check_kg_business_integration.py
```

Run the verification scripts only against a running backend connected to PostgreSQL.

---

## Task 18E Cloud Model Online Acceptance

Task 18E hardens and verifies the optional `cloud_openai` OpenAI-compatible provider.

Local configuration only:

```env
CLOUD_LLM_ENABLED=true
CLOUD_LLM_BASE_URL=<OpenAI-compatible base url>
CLOUD_LLM_API_KEY=<real api key>
CLOUD_LLM_MODEL=<model name>
CLOUD_LLM_TIMEOUT_SECONDS=60
CLOUD_LLM_MAX_TOKENS=1024
CLOUD_LLM_TEMPERATURE=0.2
```

Security rules:

- never commit `backend/.env`.
- never write real API keys into code, docs, frontend bundles, reports, or logs.
- Model Gateway status may show `api_key_configured=true`, but must not return the key value.
- request logs store prompt and safe provider metadata only; Authorization headers are not stored.
- cloud base URLs are masked in provider status and provider config summaries.

Verification:

```powershell
cd backend
uv run python scripts/check_cloud_model_online.py
```

Result modes:

- `passed`: real `cloud_openai` calls succeeded.
- `blocked`: cloud credentials are missing or disabled; fallback was verified.
- `failed`: cloud credentials are present but calls or safety checks failed.

Task 18E does not add an Alembic migration and does not introduce Docker, SQLite, pgvector, embedding, OCR, or external graph databases.

---

## Task 18F Local llama.cpp / GGUF Preparation

Task 18F prepares the optional `local_llama_cpp` Model Gateway provider for later native LoongArch/Kylin validation.

Supported local API modes:

- `openai_compatible`: `POST /v1/chat/completions`
- `llama_cpp_native`: `POST /completion`

Configuration:

```env
LOCAL_LLM_ENABLED=false
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080
LOCAL_LLM_MODEL=local-gguf-model
LOCAL_LLM_API_TYPE=openai_compatible
LOCAL_LLM_TIMEOUT_SECONDS=60
LOCAL_LLM_MAX_TOKENS=1024
LOCAL_LLM_TEMPERATURE=0.2
LOCAL_LLM_HEALTH_PATH=/health
LOCAL_LLM_NATIVE_COMPLETION_PATH=/completion
LOCAL_LLM_OPENAI_CHAT_PATH=/v1/chat/completions
```

Verification:

```powershell
cd backend
uv run python scripts/check_local_llama_cpp_flow.py
```

The script reports:

- `passed` only when real local llama.cpp calls succeed.
- `blocked` when local llama.cpp is disabled or unreachable and fallback is verified.
- `failed` when configuration exists but calls, logs, or safety checks fail.

Rules:

- do not commit `.gguf`, `.bin`, or `.safetensors` model files.
- do not log full local model paths.
- do not make backend startup depend on local llama.cpp.
- keep `rule_based` fallback available.

---

## Task 11 Record Center / Review / Statistics

Task 11 adds read-oriented record tracing and review-management APIs on top of the existing PostgreSQL schema. No Alembic migration is added.

### Added API Groups

- `GET /api/record-center/overview`
- `GET /api/record-center/search`
- `GET /api/record-center/records/{record_type}/{record_id}`
- `GET /api/record-center/devices/{device_id}/timeline`
- `GET /api/review/knowledge`
- `GET /api/review/knowledge/{document_id}`
- `POST /api/review/knowledge/{document_id}/approve`
- `POST /api/review/knowledge/{document_id}/reject`
- `POST /api/review/knowledge/{document_id}/archive`
- `POST /api/corrections`
- `GET /api/corrections`
- `GET /api/corrections/{correction_id}`
- `POST /api/corrections/{correction_id}/resolve`
- `GET /api/system/statistics`

### RBAC Summary

- `viewer`: read-only access to record center, review list/detail, system statistics, and public resolved corrections.
- `engineer`: can submit model-output corrections but cannot approve/reject/archive knowledge.
- `expert` / `admin`: can review knowledge and resolve corrections.

### Verification

---

## Task 12 Model Gateway Update

Task 12 adds a configurable model gateway without changing database schema or existing retrieval / diagnosis business flows.

### Providers

- `rule_based`: default fallback provider, no external model service required.
- `local_llama_cpp`: reserved HTTP adapter for a local llama.cpp / GGUF service.
- `cloud_openai`: reserved OpenAI-compatible cloud adapter.

### Environment

```env
MODEL_GATEWAY_DEFAULT_PROVIDER=rule_based
MODEL_GATEWAY_TIMEOUT_SECONDS=20
MODEL_GATEWAY_ENABLE_LOGGING=true
MODEL_GATEWAY_ALLOW_FALLBACK=true

LOCAL_LLM_ENABLED=false
LOCAL_LLM_BASE_URL=http://127.0.0.1:8080
LOCAL_LLM_MODEL=local-gguf-model
LOCAL_LLM_API_TYPE=openai_compatible

CLOUD_LLM_ENABLED=false
CLOUD_LLM_BASE_URL=
CLOUD_LLM_API_KEY=
CLOUD_LLM_MODEL=
CLOUD_LLM_API_TYPE=openai_compatible
```

### API

```text
GET  /api/model-gateway/status
POST /api/model-gateway/test
POST /api/model-gateway/chat
GET  /api/model-gateway/logs
GET  /api/model-gateway/logs/{log_id}
```

`POST /api/model-gateway/test` and `POST /api/model-gateway/chat` require `admin`, `expert`, or `engineer`. `viewer` can only read status and logs.

Model calls are logged to the existing `model_call_logs` table. API keys are never returned to the frontend and must not be written to logs.

```bash
cd backend
uv run python -m compileall app
uv run python -m alembic -c alembic.ini current
```

`alembic current` should remain `20260601_0002 (head)` for this task.

---

## Task 13 Model Enhancement Integration

Task 13 connects the existing Model Gateway to retrieval QA, fault diagnosis, and SOP generation as an optional enhancement layer. It does not add database fields or Alembic migrations.

### Business Request Fields

The following optional fields are supported by:

- `POST /api/retrieval/query`
- `POST /api/diagnosis/analyze`
- `POST /api/sop/generate`

```json
{
  "enable_model_enhancement": false,
  "model_provider": "rule_based",
  "allow_model_fallback": true
}
```

### Response Metadata

Enhanced business responses include:

```json
{
  "model_enhanced": false,
  "fallback_used": false,
  "model_provider": "rule_based",
  "model_name": "rule_or_gateway_model_name",
  "model_call_trace_id": null
}
```

### Safety Rules

- Rule-based retrieval, diagnosis, and SOP generation remain the stable mainline.
- Model output only enhances wording or explanation for the current response.
- Real `references`, `retrieved_chunks`, `related_history`, SOP steps, and SOP checklists are not generated by the model and must not be overwritten by it.
- Model Gateway writes calls to the existing `model_call_logs` table.
- API keys must remain server-side and must not appear in frontend responses or logs.

### Verification

```bash
cd backend
uv run python -m compileall app
uv run python -m alembic -c alembic.ini current
uv run python scripts/check_model_enhancement_flow.py
```

`alembic current` should remain `20260601_0002 (head)`. Do not run `alembic revision` for Task 13.

---

## Task 18B Knowledge Contribution APIs

Task 18B implements the frontline knowledge contribution and expert review workflow on the existing PostgreSQL schema. It does not add an Alembic migration.

API group:

```text
GET  /api/knowledge/contributions
POST /api/knowledge/contributions
GET  /api/knowledge/contributions/{contribution_id}
PUT  /api/knowledge/contributions/{contribution_id}
POST /api/knowledge/contributions/{contribution_id}/submit
POST /api/knowledge/contributions/{contribution_id}/request-changes
POST /api/knowledge/contributions/{contribution_id}/approve
POST /api/knowledge/contributions/{contribution_id}/reject
POST /api/knowledge/contributions/{contribution_id}/convert-to-document
POST /api/knowledge/contributions/{contribution_id}/archive
```

RBAC:

- `engineer`: create draft, edit own draft / changes requested / rejected items, submit for review.
- `expert` / `admin`: request changes, approve, reject, convert approved contribution to knowledge document, archive.
- `viewer`: read-only list/detail for approved or converted contributions.

Conversion behavior:

- approved contribution becomes an approved active `knowledge_documents` row.
- real `knowledge_chunks` are generated from the contribution content.
- contribution status becomes `converted` and stores `approved_document_id`.
- `knowledge_review_records` stores the workflow action history.
- `record-center` supports `record_type=knowledge_contribution`.

Verification:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python scripts/seed_final_demo_data.py
uv run python scripts/check_contribution_flow.py
uv run python -m alembic -c alembic.ini current
```

Do not run `alembic revision` or `alembic upgrade head` for Task 18B.

## Task 14A Backend Smoke and Audit

Task 14A adds read-oriented and smoke-check scripts for delivery preparation. No database schema changes or Alembic migrations are added.

### Start Backend

```powershell
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Static Checks

```powershell
cd backend
uv run python -m compileall app
uv run python -m alembic -c alembic.ini current
```

`alembic current` should remain:

```text
20260601_0002 (head)
```

### Demo Data Audit

```powershell
cd backend
uv run python scripts/demo_data_audit.py
```

The audit script is read-only. It reports test users, disposable documents, demo devices, demo knowledge, demo SOP templates, demo tasks, corrections, and suspicious QA records. It does not delete or archive data.

### Full API Smoke

```powershell
cd backend
uv run python scripts/full_smoke_check.py
```

Defaults:

```text
FULL_SMOKE_BASE_URL=http://127.0.0.1:8000/api
FULL_SMOKE_ADMIN_USERNAME=admin
FULL_SMOKE_ADMIN_PASSWORD=<set-local-admin-password>
```

The smoke script logs in as admin and checks health, system status/statistics, devices, knowledge documents, retrieval query, diagnosis analysis, SOP generation, maintenance tasks, record center, and model gateway status. Retrieval and diagnosis create traceable `Task14A_Smoke` records; no data is deleted.

---

## Task 14B Cloud Model Integration Check

Task 14B tightens the optional `cloud_openai` OpenAI-compatible adapter and adds a real integration check script. It does not create Alembic migrations and does not change business API paths.

### Cloud Configuration

`backend/.env` must explicitly contain all required values before a real cloud call is attempted:

```env
CLOUD_LLM_ENABLED=true
CLOUD_LLM_BASE_URL=https://api.example.com
CLOUD_LLM_API_KEY=
CLOUD_LLM_MODEL=compatible-chat-model
CLOUD_LLM_API_TYPE=openai_compatible
```

The adapter accepts `CLOUD_LLM_BASE_URL` values ending with either the host root, `/v1`, or `/v1/chat/completions`. API keys are sent only in the server-side `Authorization` header and must not be returned to the frontend or written to logs.

### Verification

Start the backend first:

```powershell
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then run:

```powershell
cd backend
uv run python scripts/check_cloud_model_flow.py
```

If cloud configuration is incomplete, the script reports `cloud_real_call: blocked` and validates safe rule-based fallback instead of pretending that a real cloud model call succeeded.

---

## Task 16 Backend Delivery Notes

Task 16 does not change database schema and must not execute `alembic revision` or `alembic upgrade head`.

Key backend hardening updates:

- `/api/system/status` now performs a real PostgreSQL `SELECT 1` connectivity check and returns table counts.
- Database errors are summarized by exception type only; connection strings, passwords, and API keys are not exposed.
- `scripts/create_admin_user.py` remains the supported admin repair helper.
- `scripts/cleanup_dev_test_data.py` is dry-run by default and soft-archives only safe development/test rows when explicitly confirmed.
- `scripts/seed_final_demo_data.py` creates or updates stable Huawei/Sungrow PV inverter demo data without duplicating rows.
- `backend/static/frontend` is generated output installed from `frontend/dist`; do not edit it as source code.

Useful commands:

```powershell
cd backend
uv run python scripts\create_admin_user.py
uv run python scripts\seed_final_demo_data.py
uv run python scripts\cleanup_dev_test_data.py
uv run python -m compileall app
uv run python -m alembic -c alembic.ini current
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Install frontend build output into the backend:

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
```

Run delivery smoke from the repository root while the backend is running:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
```

The default smoke test avoids write endpoints that create business records. To explicitly test retrieval query persistence, run it with `-IncludeRetrievalQuery` and then audit the generated Task16 verification record.

---

## Task 18C Knowledge Graph Backend

Task 18C adds PostgreSQL knowledge graph tables, services, and `/api/kg` endpoints.

Migration:

```powershell
cd backend
uv run python -m alembic -c alembic.ini heads
uv run python -m alembic -c alembic.ini current
uv run python -m alembic -c alembic.ini upgrade head
uv run python -m alembic -c alembic.ini current
```

Expected head after upgrade:

```text
20260601_0003
```

Demo graph scripts:

```powershell
cd backend
uv run python scripts\seed_demo_knowledge_graph.py
uv run python scripts\check_knowledge_graph_flow.py
```

The knowledge graph foundation remains PostgreSQL-only. Neo4j, pgvector, embeddings, OCR, and real LLM graph extraction are deferred.

---

## Task 18G Optional OCR Plugin Workflow

Task 18G adds a disabled-by-default OCR workflow around uploaded image media. It uses a Tesseract command-line adapter through `subprocess`; the backend does not install Tesseract, does not vendor OCR binaries, and does not add PaddleOCR/RapidOCR/deep-learning dependencies.

Configuration:

```env
OCR_ENABLED=false
OCR_PROVIDER=tesseract
OCR_LANG=chi_sim+eng
OCR_TIMEOUT_SECONDS=30
OCR_MAX_IMAGE_MB=10
OCR_TESSERACT_CMD=tesseract
```

API endpoints:

```text
GET  /api/media/ocr/status
POST /api/media/{media_id}/ocr
GET  /api/media/{media_id}/ocr
```

Permissions:

- authenticated users can read OCR status and OCR result;
- `engineer`, `expert`, and `admin` can trigger OCR;
- `viewer` cannot trigger OCR.

Acceptance commands:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
uv run python scripts\check_ocr_flow.py

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\check_tesseract_env.ps1
```

When OCR is disabled or Tesseract is unavailable, `check_ocr_flow.py` should report `blocked`; this is acceptable and must not be described as real OCR recognition success.

---

## Task 18H Final Delivery Freeze

The backend is frozen for final delivery validation with current Alembic revision:

```text
20260601_0003 (head)
```

Windows validation completed:

```powershell
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
powershell -ExecutionPolicy Bypass -File ..\scripts\final_smoke_test.ps1
uv run python scripts\check_knowledge_graph_flow.py
uv run python scripts\check_kg_business_integration.py
uv run python scripts\check_cloud_model_online.py
uv run python scripts\check_local_llama_cpp_flow.py
uv run python scripts\check_ocr_flow.py
```

Results:

- compileall: passed.
- Alembic current: `20260601_0003 (head)`.
- final smoke: passed, 23 total and 0 failed.
- KG flow and KG business integration: passed.
- cloud model: blocked/fallback; no credentials configured.
- local llama.cpp: blocked/fallback; local service disabled.
- OCR: blocked; disabled by configuration.

LoongArch/Kylin acceptance remains blocked until a real target host runs:

```bash
bash scripts/check_loongarch_kylin.sh
bash scripts/final_smoke_test.sh
```

On a new target database, `alembic upgrade head` is allowed and required. Do not create a new migration during deployment freeze.

---

## Task 18K Final API and Capability Boundary Calibration

This backend README now treats the current OpenAPI route set as the delivery baseline. Legacy record endpoints and the legacy maintenance-diagnosis endpoint name are not current public route names.

Current backend API groups:

- `/api/auth/*`
- `/api/health`
- `/api/system/*`
- `/api/users/*`
- `/api/devices/*`
- `/api/knowledge/*`
- `/api/knowledge/contributions/*`
- `/api/retrieval/query` and `/api/retrieval/records`
- `/api/diagnosis/analyze` and `/api/diagnosis/records`
- `/api/maintenance/tasks/*`
- `/api/sop/*`
- `/api/media/*`
- `/api/model-gateway/*`
- `/api/kg/*`
- `/api/review/*`
- `/api/corrections/*`
- `/api/record-center/*`

Delivery boundary:

- `20260601_0003 (head)` is the current accepted Alembic revision.
- Do not run `alembic upgrade head` during documentation cleanup tasks.
- Cloud, local llama.cpp, and OCR checks must remain `blocked` unless the required external services are explicitly configured and the corresponding real checks pass.
- Do not claim pgvector, embedding retrieval, Neo4j, image fault recognition, or LoongArch/Kylin real-machine acceptance.
## Task 24B DashVector Hybrid RAG

Task 24B uses `/api/vector-search` and DashVector index metadata tables. It does not use pgvector or store raw vectors in PostgreSQL. Local validation uses `fake_in_memory` plus `deterministic_test`; real DashVector and real embedding calls require explicit opt-in and configured environment variables.

## Task 24D Security Hardening

Backend startup now runs production security validation. In `APP_ENV=production`, unsafe placeholder `SECRET_KEY`, weak or missing `ADMIN_PASSWORD`, non-PostgreSQL `DATABASE_URL`, wildcard CORS origins, unwritable upload/log directories, or incomplete enabled real providers must be rejected or reported as blocked without exposing values.

Security scripts:

- `uv run python scripts/check_security_config_status.py`
- `uv run python scripts/check_secret_leak_scan.py`
- `uv run python scripts/check_log_sanitization.py`
- `uv run python scripts/check_upload_security.py`
- `uv run python scripts/check_rbac_security_matrix.py`

The scripts write sanitized results under `.runtime/security/`. They must not print API keys, Authorization headers, tokens, passwords, local paths, or full secret values. The local `.env` may contain configured secrets for development, but those values must be rotated if ever exposed and must not be committed.
