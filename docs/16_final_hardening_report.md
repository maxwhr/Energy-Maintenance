# Task 16 Final Hardening Report

## Scope

Task 16 hardens the first-version Energy-Maintenance delivery for Huawei and Sungrow PV inverter maintenance workflows. It does not add database migrations, Docker, SQLite, embeddings, pgvector, OCR, or mandatory LLM integration.

## Problems Addressed

- `/api/system/status` no longer reports `database_status=not_checked`; it performs a real PostgreSQL connectivity check and returns core table counts.
- Windows local startup now has explicit scripts for environment check, PostgreSQL service repair, standalone PostgreSQL startup, backend startup, backend stop, and final smoke testing.
- The active frontend source tree is `frontend/`; legacy frontend backups are documented as temporary and excluded from final delivery.
- `backend/static/frontend/` is documented as generated build output installed from `frontend/dist`.
- Important detail views were polished away from raw JSON as primary display where practical.
- Demo data and development-test cleanup scripts were added with conservative, repeatable behavior.

## PostgreSQL Startup Strategy

- Preferred final route: native PostgreSQL Windows service for local validation, and native PostgreSQL service on LoongArch/Kylin deployment.
- Local fallback: `scripts/start_postgresql_standalone.ps1` using `pg_ctl.exe`.
- Service repair helper: `scripts/fix_postgresql_service_admin.ps1 -Apply`, requiring Administrator PowerShell.
- Task 16 does not run `alembic upgrade head`.

## Security Boundaries

- `.env`, `SECRET_KEY`, `CLOUD_LLM_API_KEY`, and database passwords must not be printed in reports or committed.
- System status reports only the database exception class when offline.
- Cloud model support remains blocked/fallback unless explicitly configured.

## Remaining Hardening Items

- Confirm PostgreSQL Windows service persistence before final handoff if standalone `postgres.exe` was used.
- Remove or exclude `frontend_legacy_before_cupProject_*` from final release packaging.

## Task 16A Closeout

Task 16A completed the two frontend items previously marked partial:

- Maintenance task detail now exposes edit and reassignment controls when role, ownership, and task status permit.
- Reassignment uses the real backend assignable-user list and does not require a manually entered UUID.
- Viewer can read task list/detail and record-center data, while all task write controls remain hidden.
- Record center now provides structured detail, related-record drilldown, device selection from real results, device timeline, and timeline-item detail drilldown.
- Raw record JSON is retained only in a collapsed technical section.

PostgreSQL was checked on June 15, 2026. The `postgresql-x64-16` service exists but remains `Stopped / Disabled`. The current PowerShell session is not elevated, so no service settings were changed. Local verification used standalone PostgreSQL from `D:\Work Space\PostgreSQL`; port `127.0.0.1:5432` was reachable.

Administrator action is still required for persistent Windows startup:

```powershell
cd "D:\Work Space\Energy-Maintenance"
powershell -ExecutionPolicy Bypass -File scripts\fix_postgresql_service_admin.ps1 -Apply
Get-Service postgresql-x64-16
Test-NetConnection 127.0.0.1 -Port 5432
```

The expected final service state is `Running / Automatic`. After repair, rerun `scripts/final_smoke_test.ps1`.

## Task 17B P1 Hardening

- Formal retrieval now requires knowledge documents to be `parsed`, `active`, and `approved`; pending or unreviewed documents remain visible in management/review views but do not contribute references.
- `.env.example` uses the explicit `change-this-secret-in-production` placeholder and production admin initialization fails when `ADMIN_PASSWORD` is missing.
- Media APIs accept only jpg/jpeg/png/webp, store fault/alarm/task metadata in existing fields, and expose an authenticated inline preview endpoint.
- Retrieval and diagnosis accept validated `media_ids`; media metadata and manual descriptions may influence text context, while unparsed image content is never inferred.
- QA media summaries are stored in existing `qa_records.related_history`; diagnosis uses existing `media_ids`; media rows link through existing `qa_trace_id`, `diagnosis_record_id`, and `task_id`.
- Model prompts receive safe metadata only and explicitly prohibit image-content inference, binary payloads, and local file paths.
- Workorder completion and SOP execution forms now capture real user-entered outcomes using existing fields and JSONB, with no Alembic migration.
- The final Task 17B browser pass verified admin media entry points, protected media preview, and viewer `/403` behavior after the production build was installed.

## Task 18B Frontline Contribution Hardening

- Added `/api/knowledge/contributions` as a role-gated frontline knowledge contribution workflow on the existing `knowledge_contributions` and `knowledge_review_records` tables.
- Engineer users can create/edit/submit their own contribution drafts; expert/admin users can request changes, approve, reject, convert approved contributions to knowledge documents, or archive.
- Conversion creates an approved active `knowledge_documents` row and real `knowledge_chunks` from the contribution content, then stores `approved_document_id` on the contribution.
- Record center now supports `record_type=knowledge_contribution` and traces contribution metadata, converted document, related task/diagnosis/QA context, and media IDs where available.
- Frontend route `/knowledge/contributions` provides the create/edit/review/read-only workflow and reuses existing media evidence selection.
- No Alembic migration was added; current schema already contained the required contribution, review, document, chunk, and media fields.
- OCR, image understanding, embedding, pgvector, and mandatory LLM generation remain deferred.

## Task 18E Cloud Model Online Acceptance Hardening

- Added explicit cloud provider settings for timeout, max tokens, and temperature in backend configuration.
- Cloud provider status and model-call provider config now expose only safe metadata: `api_key_configured=true/false`, model name, API type, timeout, max token settings, and masked base URL.
- `cloud_openai` error summaries are sanitized to avoid API key or Authorization header exposure.
- `cloud_openai` status is marked `available` only after a real successful cloud call is observed in `model_call_logs`; otherwise it remains `disabled`, `not_configured`, `not_checked`, or `unavailable`.
- Added `backend/scripts/check_cloud_model_online.py` to distinguish `passed`, `blocked`, and `failed`.
- Current local `.env` does not contain real cloud credentials, so real cloud success must be reported as blocked until the user configures `CLOUD_LLM_*`.
- No Alembic migration was added. No Docker, SQLite, pgvector, embedding, OCR, or external graph database dependency was introduced.
# Task 18F Local llama.cpp / GGUF Hardening

- Added configurable local llama.cpp settings for API type, timeout, max tokens, temperature, health path, native completion path, and OpenAI-compatible chat path.
- Enhanced `local_llama_cpp` to support both `/v1/chat/completions` and native `/completion`.
- Added local health checks against `/health`, `/`, and `/props` without making backend startup depend on local model availability.
- Local model errors are classified as disabled, not_configured, unavailable, endpoint_mismatch, invalid_response, or empty_response where applicable.
- Full local model paths are not exposed in `model_name`, provider config summaries, or error messages.
- Added `backend/scripts/check_local_llama_cpp_flow.py` to distinguish `passed`, `blocked`, and `failed`.
- Added Windows and LoongArch/Kylin llama.cpp startup example scripts without downloading models or assuming llama.cpp is installed.
- No Alembic migration was added. No Docker, SQLite, pgvector, embedding, OCR, GGUF model file, or llama.cpp binary was introduced.

# Task 18G Optional OCR Plugin Hardening

- Added optional OCR configuration with `OCR_ENABLED=false` by default.
- Added a Tesseract command-line adapter through `subprocess`; the project does not install or vendor OCR binaries or language packs.
- Added `/api/media/ocr/status`, `/api/media/{media_id}/ocr`, and OCR readback support while keeping viewer accounts read-only for OCR triggering.
- Retrieval and diagnosis accept `use_ocr_text=false` by default; OCR text is only included as machine-recognized context when explicitly requested.
- Record-center media payloads can expose OCR status, provider, language, processed time, error summary, and OCR text summary from existing fields.
- Current local OCR validation is `blocked` because OCR is disabled and `tesseract` is not configured. This is expected and is not reported as real OCR success.
- No Alembic migration was added. `alembic upgrade head` was not executed. No Docker, SQLite, pgvector, embedding, PaddleOCR, RapidOCR, or deep-learning OCR dependency was introduced.

# Task 18H Final Freeze Hardening

- Added Linux/Kylin `scripts/final_smoke_test.sh` so target hosts can run smoke checks without PowerShell.
- Windows final regression passed with backend compileall, Alembic current, frontend build, static frontend install, final smoke, KG scripts, cloud fallback, local fallback, and OCR blocked-mode checks.
- `npm audit fix` updated only `frontend/package-lock.json` for `form-data` and reduced audit output to `found 0 vulnerabilities`.
- `/api/system/status` reports `database_status=online` in the current Windows runtime.
- The Windows PostgreSQL service remains `Stopped / Disabled`; local validation uses standalone `postgres.exe`, so Administrator service repair is still required for reboot-stable Windows operation.
- LoongArch/Kylin real-machine acceptance was not executed in this session and is explicitly marked `blocked`.
- No Alembic migration was added. `alembic upgrade head` was not executed on Windows. No Docker, SQLite, pgvector, embedding, model binary, or OCR binary was introduced.
