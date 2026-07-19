# Task 24C Real External API Acceptance Report

## 1. Scope

Task 24C connected the existing External API Provider Gateway to controlled real-call acceptance paths without packaging, committing, changing migrations, or exposing secrets.

The task verifies only providers that are explicitly enabled and configured in local environment variables. Disabled or incomplete providers are reported as `blocked`, not `passed` and not `failed`.

## 2. Provider Summary

- Cloud LLM: passed. The OpenAI-compatible text model was called through Model Gateway and External API Gateway. Results were parsed, logged with sanitized summaries, and kept fallback behavior available.
- MIMO / Vision: passed. A real multimodal job was executed and persisted to `media_ai_analyses` with `mocked=false`, `real_external_api_used=true`, and `human_review_status=pending`.
- OCR API: passed. A real OCR job was executed and persisted to `media_ocr_results` with non-empty recognized text, `mocked=false`, and `real_external_api_used=true`.
- DashVector: blocked. Real DashVector was not enabled and required configuration was incomplete.
- Embedding: blocked. Real embedding provider was not enabled and required configuration was incomplete.
- Cloud Vision: disabled / not first-line verified in this task.
- Local LLM and Tesseract: disabled / blocked; no model download or OCR binary installation was performed.

## 3. Real-call Result

The unified real acceptance script reported:

```text
total=5
passed=3
blocked=2
failed=0
real_external_api_used=true
```

Result files were written under `.runtime/task24c/` and contain sanitized summaries only. They must not be committed as delivery evidence unless reviewed for local environment details.

## 4. Persistence

- Cloud LLM wrote sanitized model and external API call logs.
- MIMO wrote a real analysis row in `media_ai_analyses`.
- OCR wrote a real OCR row in `media_ocr_results`.
- Agent provider integration verified that `media_mimo_analysis`, `media_ocr`, and `model_gateway_chat` can read real provider results.

Formal knowledge, SOP, KG, and task records are still protected by approval / conversion boundaries. Real model output is auxiliary evidence and must not directly replace field engineer judgment.

## 5. Security

- No API key, Authorization header, password, local absolute path, or base64 image payload was printed in reports.
- Logs store sanitized request and response summaries.
- OCR provider responses that return evidence in non-standard reasoning fields are normalized by extracting visible text only; full reasoning content is not persisted.
- Previously exposed real keys must be rotated before production or external acceptance is repeated.

## 6. Verification Commands

Executed and passed:

- `uv run python -m compileall app scripts`
- `uv run python -m alembic -c alembic.ini heads`
- `uv run python -m alembic -c alembic.ini current`
- `uv run python scripts/check_real_external_api_acceptance.py`
- `uv run python scripts/check_real_external_api_acceptance.py --allow-real-api --base-url http://127.0.0.1:8010/api`
- `uv run python scripts/check_real_agent_provider_integration.py --allow-real-api --base-url http://127.0.0.1:8010/api`
- security regression scripts
- offline DashVector / Agent / External Gateway regressions
- `npm.cmd install`
- `npm.cmd audit`
- `npm.cmd run build`
- `backend/scripts/build_and_install_frontend.ps1`
- `scripts/final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`

No `alembic upgrade head` was executed in Task 24C, and no new migration was created.

## 7. Remaining Boundaries

- DashVector and Embedding remain blocked until real configuration is supplied.
- LoongArch / Kylin real-machine deployment is not verified by this task.
- Provider availability is dependent on external API service quality and local environment configuration.
- Production deployment still requires strong `SECRET_KEY`, explicit `ADMIN_PASSWORD`, HTTPS, service supervision, backup, and operational monitoring.

## 8. No-package Confirmation

Task 24C did not generate a delivery zip, did not update `delivery/`, did not create `delivery_staging/`, did not run `Compress-Archive`, and did not execute `git add` or `git commit`.

## Task 25B Vector Provider Update

Task 25B separately completed real DashScope `text-embedding-v4` and DashVector acceptance. This does not rewrite the historical Task 24C snapshot. The Task 25B evidence is under `.runtime/task25b/` and `docs/25B_embedding_and_dashvector_real_acceptance.md`; the overall Task 25B quality gate remains failed.
