# Task 22C External API Provider Gateway Report

## Scope

Task 22C adds a reserved External API Provider Gateway for future multi-agent integrations.

The gateway is designed for later connection to:

- mimo-2.5 multimodal API
- OpenAI-compatible text model API
- OpenAI-compatible vision model API
- local llama.cpp API
- OCR API
- safety review API
- knowledge extraction API
- custom HTTP API

This task does not call any real external API. It only implements database records, provider routes, dry-run checks, blocked behavior, sanitized logs, backend API endpoints, frontend API clients, and verification scripts.

## Database

Migration:

- `backend/alembic/versions/20260601_0005_add_external_api_provider_gateway.py`
- `down_revision = 20260601_0004`

New tables:

- `external_api_providers`
- `external_api_routes`
- `external_api_call_logs`
- `external_api_health_checks`

No API key, Authorization header, full image base64, or local file path is stored in these tables.

## Default Providers

Seed script:

- `backend/scripts/seed_external_api_providers.py`

Seeded providers:

- `mimo_2_5`
- `cloud_openai`
- `cloud_openai_vision`
- `local_llama_cpp`
- `tesseract_ocr`
- `custom_ocr_api`
- `safety_rule_engine`

Most providers are disabled or not configured by default. `safety_rule_engine` is local rule-based and available, but it does not call an external API.

## Default Routes

Seeded routes:

- `agent_multimodal_mimo`: `media_mimo_analysis` -> `mimo_2_5`
- `agent_media_ocr`: `media_ocr` -> `tesseract_ocr`
- `agent_model_chat`: `model_gateway_chat` -> `cloud_openai`
- `agent_safety_review`: `safety_guard` -> `safety_rule_engine`

## API

New prefix:

- `/api/external-apis`

Endpoints:

- `GET /api/external-apis/providers`
- `GET /api/external-apis/providers/{provider_code}`
- `GET /api/external-apis/routes`
- `GET /api/external-apis/status`
- `POST /api/external-apis/providers/{provider_code}/check`
- `POST /api/external-apis/dry-run`
- `GET /api/external-apis/logs`
- `GET /api/external-apis/logs/{trace_id}`
- `GET /api/external-apis/health-checks`

Permission rules:

- viewer: read providers, status, logs, health checks
- engineer/expert/admin: dry-run
- admin: provider check

## Agent Tool Integration

Updated tools:

- `media_mimo_analysis`: reads `agent_multimodal_mimo`, returns blocked when `mimo_2_5` is not configured, writes sanitized external API call log.
- `media_ocr`: reads `agent_media_ocr`, returns existing OCR context when available; otherwise returns blocked and writes sanitized external API call log.
- `model_gateway_chat`: keeps the existing ModelGatewayService flow, records external provider route status, and does not expose API keys.

## Safety Boundaries

Task 22C explicitly preserves these boundaries:

- No real mimo API call.
- No real cloud model call.
- No real local llama.cpp call.
- No real OCR API call.
- No API key saved in database.
- No Authorization header saved in logs.
- No full base64 image saved in logs.
- No local file path saved in logs.
- No delivery zip generated.
- No Docker, SQLite, pgvector, embedding, or Neo4j introduced.

## Verification

Executed verification:

- `uv run python -m compileall app scripts`
- `uv run python -m alembic -c alembic.ini heads`
- `uv run python -m alembic -c alembic.ini current`
- `uv run python -m alembic -c alembic.ini upgrade head`
- `uv run python scripts\seed_external_api_providers.py` twice
- `uv run python scripts\check_external_api_gateway_flow.py`
- `uv run python scripts\check_agent_business_tools_flow.py`
- `npm.cmd install`
- `npm.cmd audit`
- `npm.cmd run build`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`

Current local environment:

- Backend: `http://127.0.0.1:8010`
- PostgreSQL: `127.0.0.1:55432`
- Alembic current: `20260601_0005`

## Remaining Work

- Real provider credentials are not configured.
- Real external provider compatibility is not verified.
- Full frontend Provider Gateway UI is not implemented in this task.
- mimo-2.5 actual adapter connection is deferred to a later task.

Recommended next task:

- Task 22D: multimodal evidence center database and service layer development.

## Task 22D Follow-up

Task 22D now uses the External API Provider Gateway to create blocked/dry-run media processing jobs and sanitized external API call logs for OCR and multimodal analysis routes.

The gateway remains dry-run only. It still does not call mimo-2.5, cloud vision, local model, or OCR APIs.
## Task 22E Follow-up

Task 22E extends this gateway from dry-run-only provider status checks to a reusable adapter contract with local mock-run support. The gateway still does not perform real external calls. Mock-run logs and results are sanitized and marked as `mocked=true`.
