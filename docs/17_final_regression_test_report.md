# Task 16 Final Regression Test Report

## Required Verification

| Check | Status | Notes |
| --- | --- | --- |
| `npm.cmd install` | passed | Completed in `frontend/`; 0 vulnerabilities reported. |
| `npm.cmd run build` | passed | Vue type-check and Vite production build passed. |
| `backend/scripts/build_and_install_frontend.ps1` | passed | Installed 47 frontend files into `backend/static/frontend`. |
| `uv run python -m compileall app` | passed | Backend syntax check passed. |
| `uv run python -m alembic -c alembic.ini current` | passed | Current revision remained `20260601_0002 (head)`; no upgrade executed. |
| `scripts/final_smoke_test.ps1` | passed | 21 checks passed, 0 failed; retrieval write smoke skipped by default. |
| Browser admin flow | passed | Headless Chrome/CDP verified admin login, route access, and refresh restore. |
| Browser viewer flow | passed | Headless Chrome/CDP verified viewer dashboard access and forced `/review` redirect to `/403`. |

## Task 16A Regression

| Check | Status | Notes |
| --- | --- | --- |
| `npm.cmd install` | passed | Dependencies were already current; audit reported 0 vulnerabilities. |
| `npm.cmd run build` | passed | Vue type-check and Vite production build passed after task/record-center changes. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` installed 48 files. |
| Backend compile | passed | `uv run python -m compileall app` passed. |
| Alembic current | passed | Revision remained `20260601_0002 (head)`; no revision or upgrade command was run. |
| Final smoke | passed | 21 checks passed and 0 failed. |
| Maintenance task API | passed | A Task 16A verification task was created, updated, reassigned, read through record center, queried through the device timeline, and then cancelled. |
| Admin browser | passed | Login, task edit panel, reassignment panel, record detail, related records, and device timeline were verified. |
| Viewer browser | passed | Task list remained read-only, record detail remained available, and `/review` plus `/model-service` redirected to `/403`. |

## Task 16 Execution Notes

- PostgreSQL Windows service was found as `Stopped / Disabled`.
- `127.0.0.1:5432` was reachable through the standalone PostgreSQL process during Task 16A verification.
- `scripts/fix_postgresql_service_admin.ps1` was executed in dry-run mode only; no service setting was changed.
- `bash -n scripts/check_loongarch_kylin.sh` could not run in this Windows environment because `/bin/bash` was unavailable through WSL. PowerShell and Python scripts were syntax-checked.
- Task 16A did not modify Alembic migration files and did not introduce Docker or SQLite.

## Task 17B P1 Hardening And Media Evidence Regression

| Check | Status | Notes |
| --- | --- | --- |
| Approved-only retrieval | passed | Repository candidates require `knowledge_documents.review_status = approved`, `status = active`, and `parse_status = parsed`. |
| Unreviewed knowledge exclusion | passed | The live database contained five active parsed chunks whose documents were pending review or rejected. Queries using unique pending/rejected document text returned zero formal retrieval candidates. |
| Credential hardening | passed | Production configuration rejects the placeholder `SECRET_KEY`; admin creation requires `ADMIN_PASSWORD` in production and emits a strong warning before using the local development fallback. |
| Media upload and metadata | passed | A real JPG was uploaded through `/api/media/upload`; device, manufacturer, product series, fault type, alarm code, description, and OCR state remained traceable. |
| Authenticated media preview | passed | `/api/media/{id}/content` returned HTTP 200. Browser detail view loaded the protected response as a Blob image with natural dimensions `1290 x 706`. |
| Diagnosis with media | passed | `/api/diagnosis/analyze` accepted `media_ids`, returned one media item and the OCR/image-understanding boundary notice, and persisted the diagnosis trace. |
| Retrieval with media | passed | `/api/retrieval/query` accepted `media_ids`, returned three references from approved knowledge chunks, returned one media item, and persisted the QA trace. |
| Record-center media trace | passed | The created QA and diagnosis records were found through record-center APIs with the related media summary. |
| Viewer write protection | passed | Viewer media write was rejected by the API; browser navigation to `/media` and `/review` redirected to `/403`. |
| Browser media entry points | passed | Admin browser verification found upload/select controls on diagnosis and retrieval pages and the media entry on the knowledge page. |
| OCR/image interpretation boundary | passed | OCR remained disabled/not configured; prompts and responses only use safe media metadata and do not infer image contents. |
| Frontend build | passed | `npm.cmd install` and `npm.cmd run build` completed successfully with zero reported vulnerabilities. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` completed successfully. |
| Backend compile | passed | `uv run python -m compileall app` completed successfully. |
| Alembic current | passed | Revision remained `20260601_0002 (head)`; no revision or upgrade command was run. |
| Final smoke | passed | 21 checks passed and 0 failed. |

### Task 17B Verification Data

- Media ID: `738abc83-f122-4575-8870-dee832dc28dc`
- Diagnosis trace: `diag_20260615095019_611f9e619c`
- QA trace: `qa_20260615095019_cf46940ae4`
- These rows are labeled verification evidence and were not deleted during this task.

### Task 17B Known Limits

- Media evidence is stored and shown for manual inspection, but OCR and image-content understanding are not enabled by default.
- QA media context is retained through existing JSON-compatible record fields; this task intentionally added no migration.
- SOP execution-result fields are shown only after an execution enters `in_progress`.
- The standalone PostgreSQL process remains a local validation arrangement; Windows service startup still requires administrative repair before reboot-stable operation.

## Task 18B Knowledge Contribution Regression

| Check | Status | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed after contribution service/API/script changes. |
| Frontend build | passed | `npm.cmd run build` passed after adding `/knowledge/contributions`. |
| Migration | not executed | No Alembic revision or upgrade was added for Task 18B; existing revision should remain `20260601_0002`. |
| Contribution API smoke | pending runtime rerun | Execute `uv run python scripts/check_contribution_flow.py` with backend running to validate create/submit/request-changes/approve/reject/convert. |
| Final smoke update | pending runtime rerun | `scripts/final_smoke_test.ps1` now checks `GET /api/knowledge/contributions?page=1&page_size=5`. |

Task 18B verification commands:

```powershell
cd backend
uv run python scripts/seed_final_demo_data.py
uv run python scripts/check_contribution_flow.py
uv run python -m alembic -c alembic.ini current

cd ..
powershell -ExecutionPolicy Bypass -File scripts/final_smoke_test.ps1 -IncludeRetrievalQuery
```

## Smoke Coverage

Default smoke checks:

- `GET /`
- `GET /docs`
- `GET /openapi.json`
- `GET /dashboard`
- `GET /api/health`
- `GET /api/system/status`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/system/statistics`
- `GET /api/devices`
- `GET /api/knowledge/documents`
- `GET /api/retrieval/records`
- `GET /api/diagnosis/records`
- `GET /api/sop/templates`
- `GET /api/maintenance/tasks`
- `GET /api/record-center/overview`
- `GET /api/review/knowledge`
- `GET /api/corrections`
- `GET /api/model-gateway/status`

`POST /api/retrieval/query` is skipped by default to avoid creating extra `qa_records`. It can be enabled with `-IncludeRetrievalQuery` for traceable write validation.

## Non-goals

- No `alembic revision`.
- No `alembic upgrade head`.
- No Docker or docker-compose.
- No SQLite fallback.
- No claim of real OCR, pgvector, embedding, or cloud model success without explicit configuration and execution.

## Task 18E Cloud Model Regression

| Check | Status | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed. |
| Frontend build | passed | `npm.cmd run build` passed. |
| Alembic current | passed | Current revision is `20260601_0003 (head)`. `upgrade head` was not executed. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| Cloud online script | blocked | `uv run python scripts/check_cloud_model_online.py` completed in blocked mode because local cloud credentials are absent. |
| Real cloud call | blocked until configured | Requires `CLOUD_LLM_ENABLED=true`, base URL, API key, and model in local `backend/.env`. |
| Fallback behavior | passed | In blocked mode, gateway test/chat, retrieval, diagnosis, and SOP used `rule_based` fallback and wrote model logs. |
| API key safety | passed | Script checked responses and model log list/detail for API key and Authorization exposure. |

Task 18E verification command set:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current

cd ..\frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
uv run python scripts\check_cloud_model_online.py
```
# Task 18F Local llama.cpp / GGUF Regression

| Check | Status | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed. |
| Frontend build | passed | `npm.cmd run build` passed. |
| Alembic current | passed | Current revision is `20260601_0003 (head)`. `upgrade head` was not executed. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| Local llama.cpp script | blocked | `uv run python scripts/check_local_llama_cpp_flow.py` completed in blocked mode because local llama.cpp is disabled. |
| Real local model call | blocked until a local llama.cpp server is running | Requires `LOCAL_LLM_ENABLED=true`, reachable base URL, model label, and matching API type. |
| Fallback behavior | passed | Gateway test/chat and retrieval enhancement used `rule_based` fallback in blocked mode. |
| Model path safety | passed | Script checked responses and model log list/detail for full GGUF path and Authorization exposure. |

# Task 18G Optional OCR Regression

| Check | Status | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed after recovering the interrupted diagnosis/retrieval OCR edits. |
| Frontend build | passed | `npm.cmd install` and `npm.cmd run build` passed. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` installed the production build to `backend/static/frontend`. |
| Alembic current | passed | Current revision is `20260601_0003 (head)`. `upgrade head` was not executed. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| OCR flow | blocked | `backend/scripts/check_ocr_flow.py` reported `mode=blocked` because `OCR_ENABLED=false`. |
| Tesseract environment | blocked | `scripts/check_tesseract_env.ps1` reported `status=not_configured` because `tesseract` is not in `PATH`. |
| OCR overclaim guard | passed | Documentation and UI describe OCR as machine text recognition only, not image fault recognition. |

Task 18G verification command set:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
uv run python scripts\check_ocr_flow.py

cd ..\frontend
npm.cmd install
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check_tesseract_env.ps1
```

# Task 18H Final Delivery Regression

| Check | Status | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed. |
| Alembic current | passed | Current revision is `20260601_0003 (head)`. |
| PostgreSQL status API | passed | `/api/system/status` returned `database_status=online`. |
| Frontend install | passed | `npm.cmd install` completed. |
| npm audit | passed | Initial high severity `form-data` advisory was fixed by `npm.cmd audit fix`; rerun reported `found 0 vulnerabilities`. |
| Frontend build | passed | `npm.cmd run build` passed. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` passed and copied 56 files. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| KG flow | passed | `check_knowledge_graph_flow.py` passed and verified viewer approval was blocked. |
| KG business integration | passed | `check_kg_business_integration.py` passed for KG context in retrieval, diagnosis, and SOP. |
| Cloud model | blocked | `check_cloud_model_online.py` verified rule-based fallback because cloud credentials are absent. |
| Local llama.cpp | blocked | `check_local_llama_cpp_flow.py` verified fallback because local service is disabled. |
| OCR | blocked | `check_ocr_flow.py` reported disabled OCR; Tesseract env check reported `not_configured`. |
| Linux smoke on Windows | blocked | `bash` maps to unavailable WSL in this Windows environment; run `scripts/final_smoke_test.sh` on LoongArch/Kylin. |
| LoongArch/Kylin target | blocked | No real target host was available in this session. |

No `alembic upgrade head` was executed on Windows during Task 18H. No new migration was created.

# Task 18I Global Acceptance Regression

| Check | Status | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed. |
| Alembic current | passed | Current revision is `20260601_0003 (head)`. `upgrade head` was not executed. |
| Frontend install/audit/build | passed | `npm.cmd install`, `npm.cmd audit`, and `npm.cmd run build` passed; audit reported 0 vulnerabilities. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` passed and copied 56 files. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| Final demo seed | passed | `seed_final_demo_data.py` passed after making repeated seeding preserve KG-referenced chunks instead of deleting them. |
| KG flow | passed | `check_knowledge_graph_flow.py` passed. |
| KG business integration | passed | `check_kg_business_integration.py` passed for retrieval, diagnosis, and SOP. |
| Global acceptance | passed | `check_global_acceptance.py` passed with 78 total checks, 75 passed, 3 blocked, and 0 failed. |
| Cloud model | blocked | `check_cloud_model_online.py` completed in blocked/fallback mode because credentials are absent. |
| Local llama.cpp | blocked | `check_local_llama_cpp_flow.py` completed in blocked/fallback mode because local service is disabled. |
| OCR | blocked | `check_ocr_flow.py` reported OCR disabled. |
| Security/dependency scan | passed with notes | Only placeholders, docs, local defaults, and deferred `embedding_status`/future capability mentions were found. No Dockerfile, docker-compose, SQLite, pgvector, or vector DB dependency file was found. |
| Test data cleanup | passed with notes | Dry-run matched 116 development/test rows; execute soft-archived 15 safe rows and skipped 101 immutable/audit rows. Uploaded files were not removed. |

Task 18I also added `backend/scripts/check_global_acceptance.py` and updated cleanup/demo-seed scripts. No model/schema/migration/frontend-source change was made.

Task 18I verification command set:

```powershell
cd backend
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
uv run python scripts\seed_final_demo_data.py
uv run python scripts\check_knowledge_graph_flow.py
uv run python scripts\check_kg_business_integration.py
uv run python scripts\check_cloud_model_online.py
uv run python scripts\check_local_llama_cpp_flow.py
uv run python scripts\check_ocr_flow.py
uv run python scripts\check_global_acceptance.py
uv run python scripts\cleanup_dev_test_data.py
uv run python scripts\cleanup_dev_test_data.py --execute --confirm CLEAN_DEV_TEST_DATA

cd ..\frontend
npm.cmd install
npm.cmd audit
npm.cmd run build

cd ..\backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1

cd ..
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1
```

Task 18I known blockers:

- PostgreSQL Windows service remains `Stopped / Disabled`; validation used standalone `postgres.exe`.
- LoongArch/Kylin target verification remains blocked until real target hardware is available.
- Cloud model, local llama.cpp, and OCR remain optional blocked capabilities unless explicitly configured and re-tested.

# Task 18K Documentation Interface Cleanup Regression

Task 18K is documentation-only. It does not modify backend business code, frontend business code, database schema, migrations, dependencies, or runtime data.

Updated documentation baseline:

- Legacy record endpoint examples were replaced with `/api/retrieval/records`, `/api/diagnosis/records`, and `/api/record-center/*`.
- Legacy maintenance-diagnosis examples were replaced with `/api/diagnosis/analyze`.
- Maintenance task status documentation now points to the implemented task actions: `assign`, `start`, `complete`, and `cancel`.
- Final delivery claims are calibrated to core business passed, with cloud model, local llama.cpp, OCR, PostgreSQL Windows service persistence, and LoongArch/Kylin hardware acceptance still blocked or external.

Regression boundary:

- No `alembic upgrade head` was executed for Task 18K.
- No Alembic migration was added.
- `prompt.txt` and `delivery/` remain untracked and must not be staged for final delivery.
