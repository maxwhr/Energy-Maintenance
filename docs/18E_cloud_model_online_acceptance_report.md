# 18E Cloud Model Online Acceptance Report

## Scope

Task 18E verifies the optional `cloud_openai` OpenAI-compatible route in Model Gateway.

The task does not add an Alembic migration and does not introduce Docker, SQLite, pgvector, embedding, OCR, or an external graph database.

## Configuration Source

Real cloud credentials must be configured only in local `backend/.env`:

```env
CLOUD_LLM_ENABLED=true
CLOUD_LLM_BASE_URL=<OpenAI-compatible base url>
CLOUD_LLM_API_KEY=<real api key>
CLOUD_LLM_MODEL=<model name>
CLOUD_LLM_TIMEOUT_SECONDS=60
CLOUD_LLM_MAX_TOKENS=1024
CLOUD_LLM_TEMPERATURE=0.2
```

Do not commit `.env` or real API keys.

## Result Modes

- `passed`: real cloud credentials are configured and all required `cloud_openai` calls succeed without fallback.
- `blocked`: real cloud credentials are missing or cloud is disabled; fallback is verified and no real cloud success is claimed.
- `failed`: credentials are configured, but provider calls, business enhancement, logging, or safety checks fail.

## Backend Hardening

- Cloud timeout, max tokens, and temperature are configurable.
- `cloud_openai` handles base URLs ending with domain, `/v1`, or `/v1/chat/completions`.
- Error summaries are sanitized to avoid API key or Authorization exposure.
- Provider status returns `api_key_configured=true/false` but never returns the API key.
- Cloud base URLs are masked in status and log provider config summaries.
- `cloud_openai` status becomes `available` only after a real successful cloud call is present in `model_call_logs`.
- Model call logs store provider, model, latency, success/error, prompt, response, and safe metadata.

## Prompt Safety

Retrieval, diagnosis, and SOP model prompts include:

- user/business input.
- approved references when available.
- safe knowledge graph context summary.
- safe media metadata summary.
- hard safety boundaries.

Prompts explicitly prohibit:

- invented references.
- invented graph facts.
- inferred image content from unparsed images.
- local file paths.
- binary media content.
- weakening electrical safety reminders.

## Verification Script

```powershell
cd backend
uv run python scripts/check_cloud_model_online.py
```

The script checks:

- admin login.
- `GET /api/model-gateway/status`.
- `POST /api/model-gateway/test` with `provider=cloud_openai`.
- `POST /api/model-gateway/chat` with `provider=cloud_openai`.
- retrieval model enhancement.
- diagnosis model enhancement.
- SOP model enhancement.
- prompt KG/media safety boundaries.
- model call logs.
- API key and Authorization non-exposure.

## Current Local Status

At the time of this report, local `backend/.env` did not contain the required `CLOUD_LLM_*` settings. Therefore real cloud model success must be treated as `blocked` until the user configures real credentials.

Expected blocked-mode behavior:

- direct cloud calls use `rule_based` fallback when fallback is allowed.
- business model enhancement uses `rule_based` fallback.
- `model_call_logs` are still written.
- API keys remain absent from responses and logs.

## Verification Run

Executed in the local Windows environment:

- `uv run python -m compileall app scripts`: passed.
- `uv run python -m alembic -c alembic.ini current`: passed, current revision `20260601_0003 (head)`.
- `npm.cmd install`: passed, with one existing high-severity npm audit warning.
- `npm.cmd run build`: passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1`: passed.
- `powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1`: passed, 23 total and 0 failed.
- `uv run python scripts\check_cloud_model_online.py`: blocked mode completed successfully.

Blocked-mode evidence:

- `cloud_openai` status: disabled / not configured.
- `model-gateway/test`: used `rule_based` fallback.
- `model-gateway/chat`: used `rule_based` fallback.
- retrieval enhancement: used `rule_based` fallback.
- diagnosis enhancement: used `rule_based` fallback.
- SOP enhancement: used `rule_based` fallback.
- model log list/detail safety checks: passed.
- prompt KG/media safety boundary check: passed.

## Follow-up for Real Online Acceptance

After configuring real credentials in local `.env`:

1. Start the backend.
2. Run `uv run python scripts/check_cloud_model_online.py`.
3. Confirm the script reports `passed`.
4. Confirm `GET /api/model-gateway/status` shows `cloud_openai` as `available` after the successful calls.
5. Confirm retrieval, diagnosis, and SOP responses use `model_provider=cloud_openai` and `fallback_used=false`.

Do not report real cloud integration as passed until these checks have actually succeeded.
