# Task 22E: Multimodal Adapter Contract Report

## Scope

Task 22E adds the multi-provider multimodal adapter contract layer for Energy-Maintenance. It builds reusable request construction, response parsing, result normalization, prompt templates, sanitization, dry-run, and mock-run paths for future external providers.

The implementation is focused on Huawei SUN2000 / FusionSolar and Sungrow SG photovoltaic inverter maintenance evidence workflows.

## Implemented

- External API adapter contract with `check_status`, `build_request`, `invoke`, `parse_response`, `normalize_result`, `sanitize_request`, and `sanitize_response`.
- mimo-2.5 adapter entry point with `MIMO_API_PROFILE=openai_compatible_vision | custom_http_json`.
- OpenAI-compatible text / vision adapter request builders.
- OCR HTTP API adapter entry point.
- Mock adapter for local contract verification without external network calls.
- Shared sanitizer that masks API keys, Authorization, tokens, secrets, paths, base64 images, and binary payloads.
- Prompt templates for fault scene analysis, nameplate extraction, alarm screen analysis, OCR correction, safety review, and evidence summary.
- Normalized multimodal and OCR result schemas.
- `/api/external-apis/mock-run` for admin/expert local mock verification.
- `/api/multimodal/media/{media_id}/jobs` support for `dry_run`, `mock_run`, `capability`, and `analysis_type`.
- Mock multimodal analysis persistence into `media_ai_analyses`.
- Mock OCR persistence into `media_ocr_results`.
- Agent media tools can read accepted or mocked evidence-center results.

## Boundaries

- No real mimo-2.5 API call is performed.
- No cloud vision API call is performed.
- No OCR API call or local OCR engine is invoked.
- API keys must be supplied only through `.env` in a future integration task.
- External API logs do not store API keys, Authorization headers, base64 images, local file paths, or full binary payloads.
- Mocked results are marked with `mocked=true` and `not_for_production=true`.
- Machine-recognition results are auxiliary evidence only and require human review.

## Configuration

`.env.example` reserves:

```text
MIMO_ENABLED=false
MIMO_BASE_URL=
MIMO_API_KEY=
MIMO_MODEL=mimo-2.5
MIMO_API_PROFILE=openai_compatible_vision
MIMO_TIMEOUT_SECONDS=60
MIMO_MAX_TOKENS=2048
MIMO_TEMPERATURE=0.1
```

Future real provider integration should configure `.env`, verify provider compatibility, and enable real external invocation only through `ExternalApiGateway`.

## Verification

Use:

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
$env:DATABASE_URL="postgresql+psycopg2://energy_user:energy_password@127.0.0.1:55432/energy_maintenance"
uv run python -m compileall app scripts
uv run python scripts\seed_external_api_providers.py
uv run python scripts\check_multimodal_adapter_contract.py
```

Task 22E does not add Alembic migration and must not generate delivery packages.

## Task 22F Frontend Follow-up

Task 22F adds the real frontend entry that exercises the adapter contract through backend APIs:

- provider check / dry-run / mock-run;
- OCR dry-run and mock-run;
- AI multimodal dry-run and mock-run;
- AI analysis review;
- evidence links;
- Agent Run dry-run entry.

The page remains within the same safety boundary: no real external API is called without future credential configuration and compatibility validation.
## Task 22G Follow-up

Task 22G consumes the adapter contract through registered agent tools only. The multimodal evidence agent does not construct direct external API calls inside the orchestrator.

`media_ocr` and `media_mimo_analysis` continue to use Provider Gateway dry-run/mock-run behavior. Real mimo-2.5, cloud vision, and OCR providers remain unconfigured unless a later task supplies credentials and enables real external calls.
