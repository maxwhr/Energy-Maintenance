# Task 21A Real Frontend API Integration Audit Report

## 1. Scope

This audit verifies that the merged Vue frontend is connected to real FastAPI endpoints for the first-version Energy-Maintenance scope:

- Huawei / Sungrow PV inverter maintenance
- PostgreSQL-backed documents, chunks, QA records, diagnosis records, tasks, SOP, media, review, record center, KG, model gateway
- No Docker or SQLite dependency introduced
- No fake frontend success path accepted as a real business result

The audit script added in this task is:

```text
backend/scripts/check_real_frontend_api_integration.py
```

## 2. Environment Used

The default `127.0.0.1:8000` port was occupied by another local service during this audit, so Energy-Maintenance was started on:

```text
http://127.0.0.1:8010
```

The default `127.0.0.1:5432` PostgreSQL port was occupied by Docker / WSL relay from another project. To avoid touching Docker or another project process, the Windows native PostgreSQL data directory was started temporarily on:

```text
127.0.0.1:55432
```

The backend was run with:

```text
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance
```

Alembic current revision:

```text
20260601_0003 (head)
```

## 3. Static Integration Results

The Task 21A script fetched live OpenAPI from the Energy-Maintenance backend and compared all frontend API functions against backend paths.

| Item | Result |
| --- | --- |
| Frontend pages scanned | 28 |
| Frontend API functions | 63 |
| Frontend API request calls | 67 |
| Calls matched to backend OpenAPI | 67 |
| Missing backend APIs | 0 |
| Old API hits | 0 |
| Mock / fake success hits | 0 |

Old record path cleanup completed:

```text
README.md: legacy QA record endpoint -> current retrieval record endpoint
README.md: legacy diagnosis record endpoint -> current diagnosis record endpoint
```

## 4. Page/API Matrix Summary

| Frontend area | Main API functions | Backend endpoints | Connected |
| --- | --- | --- | --- |
| Login / profile | `loginApi`, `getUserInfoApi`, `logoutApi` | `/api/auth/login`, `/api/auth/me`, `/api/auth/logout` | yes |
| Dashboard | dashboard aggregate APIs | `/api/system/statistics`, `/api/record-center/overview`, `/api/devices/statistics/summary`, `/api/maintenance/tasks`, `/api/knowledge/documents` | yes |
| Device inventory | device create/detail/update/retire/statistics | `/api/devices`, `/api/devices/{device_id}`, `/api/devices/{device_id}/retire`, `/api/devices/statistics/summary` | yes |
| Knowledge documents | upload/list/detail/chunks/reparse/delete | `/api/knowledge/documents/upload`, `/api/knowledge/documents`, `/api/knowledge/documents/{document_id}`, `/api/knowledge/documents/{document_id}/chunks`, `/api/knowledge/documents/{document_id}/reparse` | yes |
| Knowledge contributions | create/update/submit/review/convert/archive | `/api/knowledge/contributions...` | yes |
| Knowledge review | list/detail/approve/reject/archive | `/api/review/knowledge...` | yes |
| Retrieval / search | query and records | `/api/retrieval/query`, `/api/retrieval/records`, `/api/retrieval/records/{trace_id}` | yes |
| Diagnosis | analyze and records | `/api/diagnosis/analyze`, `/api/diagnosis/records`, `/api/diagnosis/records/{trace_id}` | yes |
| SOP | templates/generate/executions | `/api/sop/templates`, `/api/sop/generate`, `/api/sop/executions` | yes |
| Maintenance tasks | list/create/detail/update/assign/start/complete/cancel | `/api/maintenance/tasks...` | yes |
| Record center | overview/search/detail/timeline | `/api/record-center/overview`, `/api/record-center/search`, `/api/record-center/records/{record_type}/{record_id}`, `/api/record-center/devices/{device_id}/timeline` | yes |
| Media / OCR | upload/list/detail/content/OCR status/OCR trigger | `/api/media...`, `/api/media/ocr/status` | yes |
| Knowledge graph | overview/graph/search/business context/nodes/edges/evidence/candidates/extraction | `/api/kg...` | yes |
| Model service | status/test/chat/logs | `/api/model-gateway...` | yes |
| System users/status | users and system status/statistics | `/api/users...`, `/api/system/status`, `/api/system/statistics`, `/api/system/info` | yes |

The complete page-level matrix is emitted by the script into:

```text
.runtime/21A_real_api_integration_result.json
```

This runtime file is intentionally not committed.

## 5. Real Closed-loop Verification

The script executed real authenticated network calls against the running backend and PostgreSQL:

| Area | Result |
| --- | --- |
| Backend identity | `/api/health` returned `Energy-Maintenance`; `/api/system/status` returned `database_status=online` |
| Auth/RBAC | admin login, generated engineer/expert/viewer users, `/api/auth/me` for all roles |
| Document upload | uploaded a real markdown document through `/api/knowledge/documents/upload` |
| Document parsing | `parse_status=parsed`, `chunk_count=1` |
| Chunk query | `/api/knowledge/documents/{document_id}/chunks` returned parsed content containing the unique Task 21A phrase |
| Reparse | `/api/knowledge/documents/{document_id}/reparse` returned parsed chunks |
| Review permission | viewer approval was blocked |
| Review approval | expert approved the uploaded document |
| Retrieval | `/api/retrieval/query` returned real `references` and `retrieved_chunks` from the uploaded document |
| QA persistence | `/api/retrieval/records/{trace_id}` returned saved `references` and `suggested_steps` |
| Contributions | contribution create/submit/approve/convert-to-document verified |
| Media | upload/list/detail/content preview verified |
| OCR permission | viewer OCR trigger blocked |
| Diagnosis | `/api/diagnosis/analyze` and diagnosis record detail verified |
| SOP | template create, generate, execution create/update verified |
| Tasks | create, assign, start, complete, detail verified |
| Record center | overview, search, QA detail, device timeline verified |
| Corrections | create, resolve, list verified |
| KG | overview, graph, business context, search, viewer write blocked, candidate review permission checked |
| Model gateway | rule-based provider passed; cloud/local provider fallback paths verified as blocked |
| SPA fallback | static frontend routes returned 200 from FastAPI |

Final Task 21A script summary:

```text
status: passed
total: 100
passed: 97
blocked: 3
partial: 0
failed: 0
skipped: 0
```

The three blocked items are expected optional external capabilities:

```text
OCR engine: disabled
cloud_openai: disabled, rule_based fallback verified
local_llama_cpp: disabled, rule_based fallback verified
```

## 6. Build and Smoke Verification

Commands executed in this task:

```text
cd backend
uv run python -m compileall app scripts
```

Result: passed.

```text
cd backend
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance
uv run python -m alembic -c alembic.ini current
```

Result: passed, `20260601_0003 (head)`.

```text
cd frontend
npm.cmd install
npm.cmd audit
npm.cmd run build
```

Result: passed, `npm audit` reported 0 vulnerabilities.

```text
cd backend
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1
```

Result: passed, static frontend installed to `backend/static/frontend`.

```text
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010 -IncludeRetrievalQuery
```

Result: passed, 23 checks, 0 failed.

```text
cd backend
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance
REAL_FRONTEND_API_BASE_URL=http://127.0.0.1:8010/api
uv run python scripts\check_real_frontend_api_integration.py
```

Result: passed, 100 checks, 0 failed.

## 7. Fixes Made

- Added strict real integration audit script:
  - frontend API scan
  - backend OpenAPI comparison
  - old path scan
  - fake success marker scan
  - real knowledge upload/chunk/review/retrieval/qa-record closed loop
  - contribution-to-document retrieval verification
  - media/OCR permission verification
  - diagnosis/SOP/task/record-center/KG/model-gateway verification
  - viewer RBAC probes
- Corrected README record endpoint examples to current API:
  - `/api/retrieval/records`
  - `/api/diagnosis/records`

## 8. Known Issues

- `127.0.0.1:8000` was not Energy-Maintenance during this audit; it was occupied by another local service. Energy-Maintenance was validated on `127.0.0.1:8010`.
- `127.0.0.1:5432` was occupied by Docker / WSL relay from another project. The real native PostgreSQL verification used `127.0.0.1:55432`.
- Windows PostgreSQL service is still not repaired as a persistent service in this report; the native PostgreSQL server was started through `pg_ctl` for validation.
- PowerShell commands that spawn nested PowerShell may print conda profile encoding noise on this machine. The relevant build/smoke scripts still returned exit code 0.
- OCR, cloud OpenAI-compatible provider, and local llama.cpp provider remain optional blocked capabilities. They must not be claimed as real online/real inference passed.

## 9. Conclusion

Task 21A passed for real frontend-backend API integration and the knowledge closed loop:

```text
upload document -> create chunks -> approve -> retrieve real references -> save qa_records -> read records
```

No missing frontend API backend match was found after this task. No frontend fake-success marker was found. No legacy API-version, legacy record, or workorder-style API path is used by frontend source.
