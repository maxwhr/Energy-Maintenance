# Task 18I Global Acceptance Report

Date: 2026-06-21

Scope: global functional regression and requirement-satisfaction acceptance for the first-version Huawei/Sungrow PV inverter maintenance system.

This task did not add a migration, did not execute `alembic upgrade head`, did not introduce Docker, SQLite, pgvector, embeddings, model binaries, or OCR binaries.

## 1. Environment

| Item | Status | Evidence |
| --- | --- | --- |
| PostgreSQL runtime | passed | `127.0.0.1:5432` was listening through standalone `postgres.exe`. |
| PostgreSQL Windows service | blocked | `postgresql-x64-16` remains `Stopped / Disabled`. |
| Backend port | passed | `127.0.0.1:8000` was listening and served API/static frontend. |
| System database status | passed | `/api/system/status` reported `database_status=online`. |
| Alembic current | passed | `20260601_0003 (head)`. |
| Frontend static install | passed | `backend/scripts/build_and_install_frontend.ps1` copied 56 files to `backend/static/frontend`. |
| Untracked local files | noted | `delivery/` and `prompt.txt` remain untracked and were not staged. |

## 2. Global Acceptance Script

New script:

```text
backend/scripts/check_global_acceptance.py
```

Final run:

```powershell
cd backend
uv run python scripts\check_global_acceptance.py
```

Result:

| Metric | Count |
| --- | ---: |
| total | 78 |
| passed | 75 |
| blocked | 3 |
| partial | 0 |
| failed | 0 |
| skipped | 0 |

Blocked items are external optional dependencies only:

- OCR engine: `disabled`
- cloud model provider: `disabled`, rule-based fallback verified
- local llama.cpp provider: `disabled`, rule-based fallback verified

Created Task18I run marker:

```text
Task18I_20260621123555
```

Representative records:

- device_id: `81f3ac3e-74dd-4e9d-b332-72bfe00e0af8`
- media_id: `117b103a-2659-4e1b-b64b-a000202f9a27`
- contribution_id: `d84273cf-881d-479b-b55d-91cac3abac8c`
- document_id: `99e7eb38-6b75-4c70-8990-79f1eb2aa96b`
- chunk_count: `1`
- qa_trace_id: `qa_20260621043557_35dbe53f85`
- diagnosis_trace_id: `diag_20260621043557_68cf519b26`
- task_id: `7726e870-30df-40c4-a761-ac0ef2b9cd3a`

## 3. Core Functional Areas

| Area | Status | Notes |
| --- | --- | --- |
| auth/RBAC | passed | Admin login, created/updated Task18I engineer/expert/viewer users, verified `auth/me`, viewer write block, engineer review block, viewer KG write block. |
| devices | passed | Statistics, create, list, detail, viewer write denial. |
| maintenance records | passed | Created and listed device maintenance records. |
| knowledge documents | passed | Converted contribution into approved parsed knowledge document; chunk query returned real content. |
| knowledge review | passed | Review list showed the converted Task18I document. |
| knowledge contributions | passed | Engineer create/submit, expert approve, expert convert-to-document. |
| retrieval | passed | Retrieval returned real `references` and `retrieved_chunks` from the Task18I knowledge document, wrote `qa_records`, and included KG context. |
| media/multimodal | passed | Uploaded tiny PNG media, listed it, fetched detail, and served authenticated content preview. |
| OCR optional | blocked | OCR status is `disabled`; status/detail endpoints are stable and no OCR success is claimed. |
| diagnosis | passed | Diagnosis analyze returned trace, safety notes, and KG context; diagnosis record detail was readable. |
| SOP | passed | Created template, generated SOP with KG context, created execution, moved execution through valid transitions. |
| maintenance tasks | passed | Created, assigned, started, completed task, and produced maintenance record linkage. |
| record center | passed | Overview, global search, QA detail, and device timeline returned traceable records. |
| corrections | passed | Created and accepted model-output correction. |
| knowledge graph | passed | Overview, graph, business-context, search, and viewer write denial passed. |
| KG business integration | passed | Dedicated script verified KG context in retrieval, diagnosis, and SOP. |
| model gateway | passed/blocked | `rule_based` passed; `cloud_openai` and `local_llama_cpp` blocked with fallback verified. |
| system status | passed | Database status reported online. |
| frontend routes | passed | SPA fallback returned 200 for 12 main routes. |

## 4. Existing Script Regression

| Script / command | Status | Notes |
| --- | --- | --- |
| `scripts/final_smoke_test.ps1` | passed | 23 total / 0 failed. |
| `backend/scripts/seed_final_demo_data.py` | passed | Fixed repeatability issue when seeded chunks are already referenced by `kg_evidence_links`. |
| `backend/scripts/check_knowledge_graph_flow.py` | passed | Extraction, candidate approval, evidence visibility, and viewer denial passed. |
| `backend/scripts/check_kg_business_integration.py` | passed | KG context passed for retrieval, diagnosis, and SOP. |
| `backend/scripts/check_cloud_model_online.py` | blocked | Cloud credentials are absent; fallback verified and secrets were not exposed. |
| `backend/scripts/check_local_llama_cpp_flow.py` | blocked | Local llama.cpp is disabled; failure path and fallback verified. |
| `backend/scripts/check_ocr_flow.py` | blocked | OCR is disabled. Default `viewer` credential was unavailable, so viewer OCR permission probe was skipped by that script. |

## 5. Fixes Made During Acceptance

| File | Fix |
| --- | --- |
| `backend/scripts/check_global_acceptance.py` | Added global HTTP acceptance script covering core business modules, RBAC, external blocked/fallback states, SPA routes, and soft cleanup. |
| `backend/scripts/cleanup_dev_test_data.py` | Added `Task18I_` marker and replaced a broken replacement-character marker with a stable placeholder. |
| `backend/scripts/seed_final_demo_data.py` | Made knowledge seeding idempotent by updating/reusing existing chunks instead of deleting chunks referenced by KG evidence links. |

The `seed_final_demo_data.py` fix avoids this repeated-run failure:

```text
ForeignKeyViolation on knowledge_chunks.id referenced by kg_evidence_links.chunk_id
```

## 6. Test Data Cleanup

Global script endpoint cleanup:

- archived SOP template
- archived Task18I knowledge document
- retired Task18I device
- disabled Task18I engineer/expert/viewer users

Cleanup script:

```powershell
cd backend
uv run python scripts\cleanup_dev_test_data.py
uv run python scripts\cleanup_dev_test_data.py --execute --confirm CLEAN_DEV_TEST_DATA
```

Results:

- dry-run matched 116 development/test rows.
- execute soft-archived 15 rows.
- 101 rows were skipped as unsafe to mutate, mainly immutable logs, QA records, diagnosis records, review records, device maintenance records, and device rows.
- uploaded files were not removed.

Remaining Task18I traces are retained in immutable trace/audit tables for acceptance auditability.

## 7. Security / Dependency Scan

Commands:

```powershell
rg -n "sk-|CLOUD_LLM_API_KEY=|SECRET_KEY=|Authorization: Bearer|BEGIN .*PRIVATE" . --glob '!backend/.env' --glob '!**/node_modules/**' --glob '!**/.venv/**' --glob '!**/dist/**' --glob '!backend/static/frontend/**' --glob '!delivery/**' --glob '!**/.git/**'
rg -n "sqlite|sqlite3|duckdb|docker-compose|Dockerfile|pgvector|embedding|Chroma|FAISS|Milvus|Neo4j|Nebula" . --glob '!backend/.env' --glob '!**/node_modules/**' --glob '!**/.venv/**' --glob '!**/dist/**' --glob '!backend/static/frontend/**' --glob '!delivery/**' --glob '!**/.git/**'
rg -n "localhost:|127\.0\.0\.1:" frontend/src backend/app docs README.md --glob '!backend/.env' --glob '!**/node_modules/**' --glob '!backend/static/frontend/**'
rg --files . --glob '!**/node_modules/**' --glob '!**/.venv/**' --glob '!backend/static/frontend/**' --glob '!delivery/**' | rg -i "(^|/|\\)(Dockerfile|docker-compose\.ya?ml)$|sqlite|sqlite3|duckdb|pgvector|chroma|faiss|milvus|neo4j|nebula"
```

Interpretation:

- secrets: passed. Hits were placeholders/examples such as `.env.example`, README command examples, or script Authorization header usage. `backend/.env` was excluded and not staged.
- Docker: passed. File-level scan found no Dockerfile or docker-compose file.
- SQLite: passed. File-level scan found no SQLite/duckdb dependency file.
- pgvector/embedding: passed. Hits are deferred capability documentation and existing `embedding_status` metadata field only; no vector dependency or migration was added.
- hardcoded localhost: passed with notes. Hits are docs, default local config values, CORS allowed origins, and local validation commands. No frontend business API page hardcodes a backend origin.
- env files: passed. `.env` was not staged.

## 8. Verification Commands

| Command | Result | Notes |
| --- | --- | --- |
| `uv run python -m compileall app scripts` | passed | Backend app and scripts compile. |
| `uv run python -m alembic -c alembic.ini current` | passed | `20260601_0003 (head)`. |
| `npm.cmd install` | passed | Dependencies up to date. |
| `npm.cmd audit` | passed | 0 vulnerabilities. |
| `npm.cmd run build` | passed | Vite build passed. |
| `powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1` | passed | Static frontend installed. |
| `powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1` | passed | 23 total / 0 failed. |
| `uv run python scripts\seed_final_demo_data.py` | passed | Final demo data ready after idempotency fix. |
| `uv run python scripts\check_knowledge_graph_flow.py` | passed | KG flow passed. |
| `uv run python scripts\check_kg_business_integration.py` | passed | KG business context passed. |
| `uv run python scripts\check_global_acceptance.py` | passed | 78 total / 0 failed / 3 blocked external. |
| `uv run python scripts\check_cloud_model_online.py` | blocked | Cloud credentials absent; fallback verified. |
| `uv run python scripts\check_local_llama_cpp_flow.py` | blocked | Local llama.cpp disabled; fallback verified. |
| `uv run python scripts\check_ocr_flow.py` | blocked | OCR disabled. |
| security/dependency `rg` scans | passed with notes | Only placeholders, documentation, local defaults, and deferred fields/deferred docs. |
| `alembic upgrade head` | not executed | Explicitly forbidden for Task 18I. |

## 9. Acceptance Checklist

- backend compileall passed: passed
- frontend build passed: passed
- static frontend install passed: passed
- alembic current 20260601_0003: passed
- final_smoke_test passed: passed
- check_global_acceptance passed: passed
- KG scripts passed: passed
- cloud model status honest: passed
- local model status honest: passed
- OCR status honest: passed
- core business no failed items: passed
- blocked only external dependencies: passed
- no secrets leaked: passed
- no Docker introduced: passed
- no SQLite introduced: passed
- no pgvector/embedding introduced: passed
- migration not modified: passed
- test data cleaned or safe: passed

## 10. Requirement Satisfaction Judgment

- all development requirements except external API/model/OCR/hardware config: satisfied
- ready for final docs/PPT/video: yes, with known external/hardware blockers documented
- must fix before delivery:
  - For production Windows persistence, repair `postgresql-x64-16` service startup or document standalone process limitations.
  - Run LoongArch/Kylin real-machine acceptance on target hardware.
- should fix:
  - Configure default `viewer` test account if `check_ocr_flow.py` viewer permission probing is needed as a standalone script.
- can defer:
  - real cloud model call
  - real local llama.cpp call
  - real OCR/Tesseract recognition
  - pgvector/embedding

## 11. Known Issues

- PostgreSQL Windows service remains `Stopped / Disabled`; validation used standalone `postgres.exe`.
- LoongArch/Kylin real target acceptance remains blocked because no target host was available in this session.
- Cloud model is disabled and credentials are absent.
- Local llama.cpp is disabled.
- OCR is disabled.
- `check_ocr_flow.py` skipped its default viewer permission probe because the default `viewer` credential was unavailable; global acceptance covered main RBAC denial paths separately.
- Task 18J found older record endpoint examples in legacy docs; Task 18K cleaned the delivery-facing examples to use retrieval, diagnosis, and record-center routes.

## 12. Remaining Risks

- Standalone PostgreSQL does not survive reboot unless the Windows service is repaired or a documented startup script is used.
- Immutable acceptance traces remain in QA/diagnosis/model log tables by design; cleanup skips them to preserve traceability.
- External model/OCR capabilities must be re-tested as `passed` only after real configuration and execution.

## 13. Next Suggested Task

Task 19: final documentation, PPT, demonstration video script, and delivery-package production.
