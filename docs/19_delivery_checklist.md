# Task 16 Delivery Checklist

## Source Tree

- [ ] `frontend/` is the only active frontend source tree.
- [ ] `frontend_legacy_before_cupProject_*` is excluded from release packaging.
- [ ] `backend/static/frontend/` is regenerated from `frontend/dist`.
- [ ] `.env`, API keys, upload files, caches, and logs are excluded.

## Build

- [x] `cd frontend && npm.cmd install`
- [x] `cd frontend && npm.cmd run build`
- [x] `cd backend && powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1`
- [x] `cd backend && uv run python -m compileall app`
- [x] `cd backend && uv run python -m alembic -c alembic.ini current`
- [x] Confirm current revision is `20260601_0003`.

## Runtime

- [x] PostgreSQL is reachable on `127.0.0.1:5432` through the current standalone local process.
- [x] Admin user exists.
- [x] Backend starts on `127.0.0.1:8000`.
- [x] `scripts/final_smoke_test.ps1` passes.
- [x] `/docs` and `/openapi.json` are protected from SPA fallback.
- [x] `/dashboard` uses SPA fallback.

## Browser

- [x] Admin login works.
- [x] Dashboard loads.
- [x] System status shows real database status.
- [x] Users page works for admin.
- [x] Devices, knowledge, retrieval, diagnosis, SOP, tasks, trace, review, corrections, model service pages load.
- [x] Viewer account is read-only and protected pages redirect or return 403.

## Deployment

- [x] Windows service repair path is documented.
- [x] Standalone PostgreSQL startup is marked local-development only.
- [x] LoongArch/Kylin check script is available and read-only.
- [x] Docker is not introduced as the formal route.
- [x] SQLite is not introduced.

## Task 16A Final Packaging Steps

- [ ] Open Administrator PowerShell and run:

```powershell
cd "D:\Work Space\Energy-Maintenance"
powershell -ExecutionPolicy Bypass -File scripts\fix_postgresql_service_admin.ps1 -Apply
Get-Service postgresql-x64-16
Test-NetConnection 127.0.0.1 -Port 5432
```

- [ ] Confirm the PostgreSQL service is `Running` with startup type `Automatic`.
- [ ] Exclude or remove `frontend_legacy_before_cupProject_*` from the release archive. Do not package it as an active frontend.
- [ ] Regenerate `backend/static/frontend` with `backend/scripts/build_and_install_frontend.ps1`.
- [ ] Run `scripts/final_smoke_test.ps1` against the final installed build.
- [ ] On real LoongArch/Kylin hardware, run `scripts/check_loongarch_kylin.sh` and record the result. Windows validation is not a substitute for this hardware check.

## Capability Claims

- [ ] Cloud model success is not claimed unless configured and tested.
- [x] Media upload and evidence association are documented separately from OCR/image understanding.
- [x] OCR and image fault recognition are marked deferred/not formally integrated.
- [x] Embeddings and pgvector are marked deferred/not formally integrated.
- [x] Formal retrieval excludes unreviewed knowledge and only uses approved active parsed documents.
- [x] Production setup requires explicit `ADMIN_PASSWORD` and replacement of the placeholder `SECRET_KEY`.
- [x] Verify media upload, authenticated preview, diagnosis `media_ids`, retrieval `media_ids`, and record-center media trace against the final runtime.
- [x] Run `cd backend && uv run python scripts/seed_final_demo_data.py` after Task 18B changes.
- [x] Run global acceptance and confirm engineer/expert/viewer contribution permissions.
- [x] Confirm retrieval write coverage through `backend/scripts/check_global_acceptance.py`.
- [x] Confirm `/knowledge/contributions` is present in the installed frontend route set and viewer access is read-only.

## Task 18E Cloud Model Checklist

- [ ] Configure real cloud model credentials only in local `backend/.env` if online cloud verification is required.
- [ ] Do not commit `backend/.env`, API keys, Authorization headers, or raw secret-bearing logs.
- [ ] Run `cd backend && uv run python scripts/check_cloud_model_online.py`.
- [ ] If credentials are missing, record result as `blocked`, not `passed`.
- [ ] If credentials are configured, confirm `cloud_openai` test/chat calls succeed without fallback.
- [ ] Confirm retrieval, diagnosis, and SOP model enhancement can use `cloud_openai` when configured.
- [ ] Confirm fallback to `rule_based` remains available when cloud is disabled or missing.
- [ ] Confirm `model_call_logs` do not expose API keys or Authorization headers.
- [ ] Confirm Model Gateway status displays `api_key_configured` and masked base URL only.
# Task 18F Local llama.cpp Checklist

- [ ] Do not commit `.gguf`, `.bin`, `.safetensors`, llama.cpp build outputs, or real model paths.
- [ ] Configure `LOCAL_LLM_*` only in local `backend/.env` when a local llama.cpp server exists.
- [ ] Run `cd backend && uv run python scripts/check_local_llama_cpp_flow.py`.
- [ ] If local llama.cpp is missing or disabled, record result as `blocked`, not `passed`.
- [ ] If local llama.cpp is running, confirm `model-gateway/test` and `model-gateway/chat` use `local_llama_cpp` without fallback.
- [ ] Confirm fallback to `rule_based` remains available.
- [ ] Confirm `model_call_logs` do not expose full local GGUF paths.
- [ ] On LoongArch/Kylin, run `scripts/check_loongarch_kylin.sh` and record whether `llama-server` exists.

# Task 18G Optional OCR Checklist

- [x] OCR remains disabled by default through `OCR_ENABLED=false`.
- [x] OCR uses an optional Tesseract command-line adapter and does not install or vendor OCR binaries.
- [x] `GET /api/media/ocr/status` is available before dynamic media routes.
- [x] Retrieval and diagnosis keep `use_ocr_text=false` by default.
- [x] OCR text, when present, is described as machine-recognized reference text only.
- [x] OCR text is not treated as approved knowledge and references still come from real `knowledge_chunks`.
- [x] `scripts/check_tesseract_env.ps1` reports missing Tesseract as `not_configured`.
- [x] `backend/scripts/check_ocr_flow.py` reports disabled OCR as `blocked`, not `passed`.
- [x] No Alembic migration was added and `alembic upgrade head` was not executed for Task 18G.
- [x] No Docker, SQLite, pgvector, embedding, PaddleOCR, RapidOCR, or deep-learning OCR dependency was introduced.

# Task 18H Final Freeze Checklist

- [x] Windows backend compileall passed.
- [x] Alembic current is `20260601_0003 (head)`.
- [x] `/api/system/status` reports `database_status=online`.
- [x] `npm audit fix` was applied safely and `npm audit` now reports 0 vulnerabilities.
- [x] Frontend build passed.
- [x] Static frontend was regenerated under `backend/static/frontend`.
- [x] Final smoke passed with 23 total and 0 failed.
- [x] KG flow script passed.
- [x] KG business integration script passed.
- [x] Cloud model status is honestly reported as blocked/fallback.
- [x] Local llama.cpp status is honestly reported as blocked/fallback.
- [x] OCR status is honestly reported as blocked/not_configured.
- [x] Linux/Kylin smoke script `scripts/final_smoke_test.sh` is present.
- [x] Delivery package strategy excludes `.env`, node_modules, logs, PostgreSQL data, uploads, model files, OCR binaries, tessdata, and `prompt.txt`.
- [x] `backend/static/frontend` is intentionally included as the demonstration static frontend.
- [ ] Run `scripts/check_loongarch_kylin.sh` on real LoongArch/Kylin hardware.
- [ ] Run `scripts/final_smoke_test.sh` on real LoongArch/Kylin hardware after deployment.
- [ ] Execute `alembic upgrade head` only on a target database that requires initialization.
- [ ] Repair Windows PostgreSQL service persistence from Administrator PowerShell if Windows will be used after reboot.

# Task 18I Global Acceptance Checklist

- [x] `backend/scripts/check_global_acceptance.py` exists.
- [x] Global acceptance logged in as admin and prepared Task18I engineer/expert/viewer users.
- [x] Task18I test data used the `Task18I_` prefix.
- [x] Auth/RBAC passed, including viewer write denial and engineer review denial.
- [x] Devices, maintenance records, media, knowledge contribution, knowledge document/chunk, retrieval, diagnosis, SOP, maintenance task, record center, corrections, KG, model gateway, system status, and SPA route checks passed.
- [x] Retrieval returned real references and retrieved chunks from the Task18I converted knowledge document.
- [x] `qa_records` persistence was verified through retrieval records and record-center tracing.
- [x] KG business enhancement was verified through dedicated KG scripts and global acceptance.
- [x] Cloud model status is honestly reported as blocked/fallback.
- [x] Local llama.cpp status is honestly reported as blocked/fallback.
- [x] OCR status is honestly reported as blocked.
- [x] `seed_final_demo_data.py` is repeatable when demo chunks are referenced by KG evidence links.
- [x] `cleanup_dev_test_data.py` recognizes `Task18I_` and remains dry-run by default.
- [x] Cleanup dry-run and execute were run; safe rows were soft-archived and immutable trace/audit rows were skipped.
- [x] Security/dependency scan found no real secret leak, no Dockerfile/docker-compose file, no SQLite dependency, and no pgvector/vector DB dependency file.
- [x] No Alembic migration was added or modified.
- [x] `alembic upgrade head` was not executed for Task 18I.
- [x] `delivery/` and `prompt.txt` remain untracked and were not staged.
- [ ] Run `scripts/check_loongarch_kylin.sh` on real LoongArch/Kylin hardware.
- [ ] Repair Windows PostgreSQL service persistence if Windows reboot resilience is required.

# Task 18K Final Documentation Cleanup Checklist

- [x] Legacy record API examples are replaced with `/api/retrieval/records`, `/api/diagnosis/records`, and `/api/record-center/*`.
- [x] Legacy diagnosis API examples are replaced with `/api/diagnosis/analyze`.
- [x] Delivery documents state that cloud model, local llama.cpp, OCR, and LoongArch/Kylin hardware acceptance remain blocked until configured and re-tested.
- [x] Delivery documents state that pgvector, embedding retrieval, Neo4j, and image fault auto-recognition are not completed first-version capabilities.
- [x] No migration was added for Task 18K.
- [x] `alembic upgrade head` was not executed for Task 18K.
- [x] `prompt.txt` and `delivery/` remain untracked and must not be included in release packaging.
- [ ] Final release archive excludes `prompt.txt`, `delivery/`, `.env`, node_modules, PostgreSQL data, uploads, logs, model files, OCR binaries, and tessdata.

# Task 18L Delivery Package Checklist

- [x] `.gitignore` excludes `delivery/`, `delivery_staging/`, and `prompt.txt`.
- [x] Delivery package naming format is `Energy-Maintenance_delivery_<timestamp>_<commit>.zip`.
- [x] Latest verified package: `Energy-Maintenance_delivery_20260621_133929_8c8badc.zip`.
- [x] Latest verified package size: 5,682,336 bytes.
- [x] Delivery package is generated under local `delivery/` and must not be committed.
- [x] Package validation must scan for forbidden content before release.
- [x] Package validation must confirm required files, migrations, scripts, and `backend/static/frontend` are present.
- [x] Latest package forbidden-content scan passed with `forbidden_count=0`.
- [x] Latest package required-file scan passed.
- [x] `prompt.txt`, `.env`, node_modules, frontend/dist, model files, OCR binaries, and nested delivery archives are excluded from the latest package.
- [ ] Final package archive is attached or transferred through the agreed external delivery channel, not through Git.

# Task 20B Product Acceptance Checklist

- [x] Product positioning is focused on Huawei and Sungrow PV inverter maintenance.
- [x] Core product loop is suitable for controlled demo: device, knowledge, retrieval, diagnosis, SOP, task, record center, media evidence, and knowledge graph.
- [x] Role coverage is documented for admin, expert, engineer, viewer, new maintainer, field maintainer, judges, acceptance teachers, follow-up developers, and deployment operators.
- [x] Recommended demo path is documented in `docs/20B_product_acceptance_report.md`.
- [x] Cloud model, local llama.cpp, OCR, LoongArch/Kylin real-machine acceptance, and PostgreSQL Windows service persistence remain explicitly blocked or partial.
- [x] Model gateway is positioned as extensibility/fallback status unless real providers are configured and re-tested.
- [x] OCR/image understanding is not claimed as a completed real capability.
- [x] PostgreSQL knowledge graph is described as lightweight PostgreSQL-backed KG, not Neo4j or an external graph database.
- [x] Product risks and future P0/P1/P2 priorities are documented.
- [ ] Clean or reseed final demo data before public recording if old Task verification records or mojibake-like text appear in the UI.

# Task 20C User Acceptance Checklist

- [x] Real browser login as admin was verified against the running local app.
- [x] Admin route trial covered dashboard, devices, knowledge documents, contributions, retrieval, diagnosis, SOP, tasks, record center, media, KG, model service, system status, review, and user management.
- [x] Viewer browser trial verified reduced menu visibility and forced restricted-route redirects to `/403`.
- [x] `Task20C_` API workflow trial passed with 78 total checks, 75 passed, 3 blocked, 0 failed, and 0 skipped.
- [x] Device, maintenance record, media, contribution, approval, conversion, retrieval, diagnosis, SOP, task, record center, KG, and model fallback workflows were exercised.
- [x] OCR, cloud model, and local llama.cpp were recorded as blocked rather than passed.
- [x] `Task20C_engineer`, `Task20C_expert`, and `Task20C_viewer` were disabled after the trial.
- [x] Task20C test device was retired, converted document was archived, and SOP template was archived.
- [x] QA, diagnosis, task, maintenance, SOP execution, media, contribution, and correction records were retained as audit traces.
- [ ] Clean or reseed final demo data before public recording; current UI can expose old Task markers and some encoded text from historical records.

# Task 24D Security Hardening Checklist

- [x] Production startup security validation was added.
- [x] CORS settings are loaded from backend settings and wildcard production origins are blocked.
- [x] Request body size middleware is present and oversized JSON requests return 413.
- [x] Lightweight in-memory rate limit middleware is present.
- [x] Secret scan script writes sanitized results and does not print key values.
- [x] Log sanitization script verifies API key, Authorization, token, password, base64, and local path redaction.
- [x] Upload security script verifies extension, size, traversal, absolute-path filename, viewer write blocking, and preview behavior.
- [x] RBAC matrix script verifies admin, expert, engineer, viewer, and anonymous boundaries across core modules.
- [x] `/api/system/status` exposes only sanitized security status.
- [x] Frontend system status page displays sanitized security state without secrets.
- [x] No migration was added for Task 24D.
- [x] No delivery zip was generated for Task 24D.
- [x] No `git add` or `git commit` was executed for Task 24D.
- [ ] Rotate any real DashVector / model / OCR / MIMO keys that were exposed outside the repository before production use.
- [ ] Run LoongArch/Kylin real-machine acceptance before claiming native deployment completion.

# Task 24E Agent Conversion Audit Checklist

- [x] `agent_artifact_conversions` migration added with unique artifact-target constraint.
- [x] Agent conversion service uses conversion records as the primary audit source.
- [x] Duplicate/concurrent conversion is blocked from creating duplicate formal objects.
- [x] Conversion history APIs are available for artifact and run lookup.
- [x] Frontend Agent Workbench displays conversion history and trace information.
- [x] Viewer/engineer conversion is blocked.
- [x] Pending/rejected approval conversion is blocked.
- [x] Failed conversion is recorded as `failed` with sanitized error message.
- [x] No delivery zip was generated for Task 24E.
- [x] No `git add` or `git commit` was executed for Task 24E.
