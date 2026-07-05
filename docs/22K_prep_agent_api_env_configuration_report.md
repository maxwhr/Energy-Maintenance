# Task 22K-Prep Agent API Environment Configuration Report

## 1. Scope

This report audits the current external API provider configuration surface before real Agent API integration.

Task boundary:

- No delivery package was generated.
- No `delivery/` or `delivery_staging/` update was made.
- No real external API call was made.
- No real API key was read, printed, written, or committed.
- `backend/.env` was only inspected as key presence / empty state, not as secret values.
- No migration was generated.
- `alembic upgrade head` was not executed.

## 2. Files Read

Configuration:

- `backend/app/core/config.py`
- `backend/.env.example`
- `backend/.env` key presence only, values not disclosed

Provider gateway and adapters:

- `backend/app/services/external_api_provider_registry.py`
- `backend/app/services/external_api_gateway.py`
- `backend/app/services/external_api_sanitizer.py`
- `backend/app/services/external_api_adapters/__init__.py`
- `backend/app/services/external_api_adapters/base.py`
- `backend/app/services/external_api_adapters/blocked_adapter.py`
- `backend/app/services/external_api_adapters/mimo_multimodal_adapter.py`
- `backend/app/services/external_api_adapters/openai_compatible_adapter.py`
- `backend/app/services/external_api_adapters/ocr_api_adapter.py`
- `backend/app/services/external_api_adapters/mock_adapter.py`
- `backend/app/services/external_api_request_builder.py`
- `backend/app/services/external_api_response_parser.py`
- `backend/app/services/multimodal_result_normalizer.py`

Agent runtime and tools:

- `backend/scripts/seed_agent_runtime.py`
- `backend/app/services/agent_tool_registry.py`
- `backend/app/services/agent_runtime_service.py`
- `backend/app/services/agent_tool_executor.py`
- `backend/app/services/agent_orchestrators/*.py`
- `backend/app/services/agent_tools/*.py`

API and schema:

- `backend/app/api/routes/external_apis.py`
- `backend/app/api/routes/multimodal_evidence.py`
- `backend/app/api/routes/agents.py`
- `backend/app/schemas/external_api.py`
- `backend/app/schemas/multimodal_evidence.py`
- `backend/app/schemas/agent.py`

Frontend API/read-only integration:

- `frontend/src/views/agent/Workbench.vue`
- `frontend/src/views/multimodal/index.vue`
- `frontend/src/api/externalApis.ts`
- `frontend/src/api/multimodal.ts`
- `frontend/src/api/agents.ts`

Reference reports:

- `docs/22C_external_api_provider_gateway_report.md`
- `docs/22D_multimodal_evidence_center_report.md`
- `docs/22E_multimodal_adapter_contract_report.md`
- `docs/22G_multimodal_evidence_agent_orchestration_report.md`
- `docs/22H_diagnosis_sop_task_agent_orchestration_report.md`
- `docs/22I_knowledge_curator_agent_report.md`
- `docs/22J_agent_artifact_conversion_report.md`

## 3. Agent Inventory

Current default Agent definitions from `agent_tool_registry.py`:

| Agent code | Display name | Default tools | External API dependency |
| --- | --- | --- | --- |
| `multimodal_evidence_agent` | 多模态证据智能体 | `media_lookup`, `media_ocr`, `media_mimo_analysis`, `safety_guard` | Yes, through OCR / MIMO Provider Gateway routes |
| `retrieval_qa_agent` | 检索问答智能体 | knowledge/retrieval tools | No direct external API in current implementation |
| `fault_diagnosis_agent` | 故障诊断智能体 | `diagnosis_rule_engine`, `knowledge_search`, `safety_guard` plus orchestrator context tools | Mostly local/rule/database; `safety_guard` has a Provider Gateway route but currently local rule-based |
| `sop_planner_agent` | SOP 编排智能体 | `sop_generator`, `safety_guard`, `knowledge_search` | Mostly local/rule/database |
| `task_orchestration_agent` | 工单编排智能体 | device/history/record/task draft/safety/human approval tools | Mostly local/rule/database |
| `knowledge_curator_agent` | 知识沉淀智能体 | knowledge/KG/safety/approval/draft tools | Mostly local/rule/database |
| `safety_guard_agent` | 安全合规智能体 | `safety_guard`, `record_center_lookup` | Local rule engine now; cloud safety fallback is only reserved |

Registered tool classes:

- `knowledge_search`
- `kg_business_context`
- `device_lookup`
- `device_history`
- `media_lookup`
- `media_ocr`
- `media_mimo_analysis`
- `diagnosis_rule_engine`
- `sop_generator`
- `task_draft_creator`
- `knowledge_contribution_draft_creator`
- `record_center_lookup`
- `correction_submitter`
- `safety_guard`
- `human_approval`
- `model_gateway_chat`

## 4. Agent API Dependency Matrix

| Tool | Primary provider route | Provider priority | ENV keys | Current behavior |
| --- | --- | --- | --- | --- |
| `media_mimo_analysis` | `agent_multimodal_mimo` | `mimo_2_5`, fallback `cloud_openai_vision` | `MIMO_BASE_URL`, `MIMO_API_KEY`, `MIMO_MODEL`, `MIMO_API_PROFILE`; fallback `CLOUD_VISION_*` | Reads existing accepted/mocked analysis first. Otherwise calls Provider Gateway dry-run and returns blocked. No real external call. |
| `media_ocr` | `agent_media_ocr` | `tesseract_ocr`, fallback `custom_ocr_api`, `mimo_2_5` | local OCR: `OCR_*`; API OCR: `OCR_API_*`; fallback `MIMO_*` | Reads existing OCR result first. Otherwise dry-run/blocked unless mock-run is explicitly used. No real OCR call. |
| `model_gateway_chat` | `agent_model_chat` | `cloud_openai`, fallback `local_llama_cpp` | `CLOUD_LLM_*`, `LOCAL_LLM_*` | Uses current ModelGatewayService with rule-based provider, and records Provider Gateway dry-run state. No external model call through Provider Gateway. |
| `safety_guard` | `agent_safety_review` | `safety_rule_engine`, fallback `cloud_openai` | local provider none; cloud fallback `CLOUD_LLM_*` | Local rule-based safety checklist. External cloud safety fallback is reserved only. |
| `diagnosis_rule_engine` | none | none | none | Local rule/service logic. |
| `sop_generator` | none | none | none | Local SOP draft generation. |
| `knowledge_search` | none | none | none | PostgreSQL keyword retrieval over project knowledge. |
| `kg_business_context` | none | none | none | Local PostgreSQL knowledge-graph/business context. |
| `task_draft_creator` | none | none | none | Draft artifact only; no formal write unless later converted/approved. |
| `knowledge_contribution_draft_creator` | none | none | none | Draft artifact only. |
| `correction_submitter` | none | none | none | Draft artifact only. |

## 5. Provider ENV Mapping

| Provider | Type | Priority | Required ENV keys | Optional/tuning ENV keys | Current status |
| --- | --- | --- | --- | --- | --- |
| `mimo_2_5` | `multimodal_model` | 1 | `MIMO_BASE_URL`, `MIMO_API_KEY`, `MIMO_MODEL` | `MIMO_ENABLED`, `MIMO_API_PROFILE`, `MIMO_TIMEOUT_SECONDS`, `MIMO_MAX_TOKENS`, `MIMO_TEMPERATURE` | Reserved / blocked by default |
| `cloud_openai` | `text_model` | 2 | `CLOUD_LLM_BASE_URL`, `CLOUD_LLM_API_KEY`, `CLOUD_LLM_MODEL` | `CLOUD_LLM_ENABLED`, `CLOUD_LLM_API_TYPE`, `CLOUD_LLM_TIMEOUT_SECONDS`, `CLOUD_LLM_MAX_TOKENS`, `CLOUD_LLM_TEMPERATURE` | Reserved / not configured by default |
| `cloud_openai_vision` | `vision_model` | 3 | `CLOUD_VISION_BASE_URL`, `CLOUD_VISION_API_KEY`, `CLOUD_VISION_MODEL` | `CLOUD_VISION_ENABLED` | Reserved / not configured by default |
| `custom_ocr_api` | `ocr_provider` | 4 | `OCR_API_BASE_URL`, `OCR_API_KEY`, `OCR_API_MODEL` | `OCR_API_ENABLED` | Reserved / not configured by default |
| `local_llama_cpp` | `local_model` | Optional fallback | `LOCAL_LLM_BASE_URL`, `LOCAL_LLM_MODEL` | `LOCAL_LLM_ENABLED`, `LOCAL_LLM_API_TYPE`, `LOCAL_LLM_TIMEOUT_SECONDS`, `LOCAL_LLM_MAX_TOKENS`, `LOCAL_LLM_TEMPERATURE`, `LOCAL_LLM_HEALTH_PATH`, `LOCAL_LLM_NATIVE_COMPLETION_PATH`, `LOCAL_LLM_OPENAI_CHAT_PATH`, `LOCAL_LLM_API_KEY` | Reserved / not configured by default |
| `tesseract_ocr` | `ocr_provider` | Optional local OCR | none | `OCR_ENABLED`, `OCR_PROVIDER`, `OCR_LANG`, `OCR_TIMEOUT_SECONDS`, `OCR_MAX_IMAGE_MB`, `OCR_TESSERACT_CMD` | Disabled by default; OCR is not installed by this task |
| `safety_rule_engine` | `safety_provider` | Built-in local | none | none | Available local rule engine |

Configuration gap:

- `LOCAL_LLM_API_KEY` is referenced by `external_api_provider_registry.py` as `api_key_env_key`.
- `ExternalApiGateway` can still read it with `os.getenv`.
- `app.core.config.Settings` does not currently declare `LOCAL_LLM_API_KEY`.
- Because `local_llama_cpp.requires_api_key=false`, this is not blocking, but Task 22K may add a typed Settings field for clarity if a local endpoint requires an auth token.

## 6. Generated Template

Generated:

- `backend/.env.agent-api.template`

The template contains placeholders only. It does not contain real API keys.

Recommended local development values in the template:

```text
PORT=8010
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance
```

Reason:

- In the current multi-project Windows environment, `8000` and `5432` may be occupied by other projects.
- Energy-Maintenance validation has recently used backend `8010` and Windows-native PostgreSQL `55432`.

## 7. Recommended .env Fill Order

Recommended priority:

1. Core local runtime:
   - `PORT`
   - `DATABASE_URL`
   - `SECRET_KEY`
2. MIMO 2.5 multimodal provider:
   - `MIMO_ENABLED=true`
   - `MIMO_BASE_URL`
   - `MIMO_API_KEY`
   - `MIMO_MODEL=mimo-2.5`
   - `MIMO_API_PROFILE=openai_compatible_vision` or provider-specific value confirmed by API docs
3. Cloud text model:
   - `CLOUD_LLM_ENABLED=true`
   - `CLOUD_LLM_BASE_URL`
   - `CLOUD_LLM_API_KEY`
   - `CLOUD_LLM_MODEL`
4. Cloud vision fallback:
   - `CLOUD_VISION_ENABLED=true`
   - `CLOUD_VISION_BASE_URL`
   - `CLOUD_VISION_API_KEY`
   - `CLOUD_VISION_MODEL`
5. OCR API or local OCR:
   - API OCR: `OCR_API_ENABLED=true`, `OCR_API_BASE_URL`, `OCR_API_KEY`, `OCR_API_MODEL`
   - local OCR: `OCR_ENABLED=true`, `OCR_TESSERACT_CMD`, `OCR_LANG`
6. Optional local llama.cpp:
   - `LOCAL_LLM_ENABLED=true`
   - `LOCAL_LLM_BASE_URL`
   - `LOCAL_LLM_MODEL`

Do not paste real credentials into `.env.example` or this template. Put real credentials only in `backend/.env`.

## 8. Real-call Readiness

Filling `backend/.env` is not sufficient to make real external calls in the current code.

Current real-call blockers in code:

- `ExternalApiGateway._provider_config()` hard-codes `real_external_calls_enabled=False`.
- `ExternalApiGateway._invoke_adapter()` uses adapter dry-run unless `mock_run` is requested.
- `ExternalApiGateway._to_gateway_result()` always returns `external_api_called=False`.
- `ExternalApiAdapter.invoke()` constructs sanitized requests and returns `would_call` or `blocked`; it does not make HTTP calls.
- `MimoMultimodalAdapter.invoke()`, `OpenAICompatibleAdapter.invoke()`, and `OcrApiAdapter.invoke()` currently decorate dry-run results and expose future entry points only.
- `mock_run` creates local mocked contract results and is marked not for production.

Task 22K real-call implementation should modify these entry points:

- `backend/app/services/external_api_gateway.py`
  - Add an explicit, audited real-call mode.
  - Keep dry-run/mock-run as the default.
  - Set `external_api_called=true` only after a real network call succeeds or fails at the provider layer.
  - Keep sanitized logs and no secret persistence.
- `backend/app/services/external_api_adapters/mimo_multimodal_adapter.py`
  - Implement real mimo-2.5 request execution after API contract confirmation.
  - Support the configured `MIMO_API_PROFILE`.
- `backend/app/services/external_api_adapters/openai_compatible_adapter.py`
  - Implement OpenAI-compatible text and vision calls when enabled and configured.
- `backend/app/services/external_api_adapters/ocr_api_adapter.py`
  - Implement external OCR HTTP calls when enabled and configured.
- `backend/app/services/external_api_response_parser.py`
  - Parse real provider responses into normalized structures.
- `backend/app/services/multimodal_result_normalizer.py`
  - Preserve normalized result contracts for real responses.
- `backend/app/services/multimodal_evidence_service.py`
  - Convert real provider results into `media_ocr_results` / `media_ai_analyses` with `mocked=false`.
- `backend/app/services/agent_tools/media_tools.py`
  - Use real gateway results only when explicitly requested by a future Task 22K mode.
- `backend/app/services/agent_tools/model_tools.py`
  - Preserve existing rule-based fallback and add explicit external route status for real calls.

## 9. Unified Validation Steps After Adding Real API Keys

After the user provides real credentials in `backend/.env`, run only in a controlled Task 22K implementation/acceptance task:

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
$env:DATABASE_URL="postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance"

uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
uv run python scripts\seed_external_api_providers.py
uv run python scripts\check_external_api_gateway_flow.py
uv run python scripts\check_multimodal_adapter_contract.py
```

For real online checks in Task 22K, add or extend scripts so they clearly separate:

- configuration check
- dry-run
- real provider network call
- response parsing
- sanitized log assertion
- no API key / Authorization / base64 / local path leakage
- media evidence persistence with `mocked=false`
- Agent tool integration

## 10. Validation Commands Run In This Prep Task

All commands below were run with:

```powershell
$env:DATABASE_URL="postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance"
```

| Command | Result | Notes |
| --- | --- | --- |
| `uv run python -m compileall app scripts` | passed | Python compile check passed. PowerShell profile warning was printed but command exit code was 0. |
| `uv run python -m alembic -c alembic.ini current` | passed | Current revision: `20260601_0006 (head)`. No migration upgrade was executed. |
| `uv run python scripts\seed_external_api_providers.py` | passed | `providers=7 routes=4 idempotent=true`. |
| `uv run python scripts\check_external_api_gateway_flow.py` | passed | 14 checks passed. Confirmed `real_external_calls_enabled=false`, dry-run blocked behavior, viewer 403, sanitized logs. Existing `zip_count=2` was detected, but no package was generated by this task. |
| `uv run python scripts\check_multimodal_adapter_contract.py` | passed | 13 checks passed. Confirmed dry-run blocked, mock-run local contract flow, viewer 403, sanitized logs, and no package generation by this task. |

## 11. Safety / Boundary Confirmation

- No real mimo-2.5 API call was made.
- No real cloud text model API call was made.
- No real cloud vision API call was made.
- No real OCR API call was made.
- No local OCR install or OCR execution was performed.
- No local llama.cpp model was downloaded or invoked.
- No API key was printed.
- No Authorization header was logged.
- No full base64 image was logged.
- No local file path was stored in external API logs by this task.
- No delivery zip was generated.
- No `delivery/` or `delivery_staging/` directory was updated by this task.

## 12. Next Task Recommendation

Next suggested task:

```text
Task 22K：真实外部 API 配置接入与 Provider 在线验收
```

Task 22K should start with mimo-2.5 because it is the highest-value missing real provider for the multimodal evidence agent. It should remain opt-in, auditable, timeout-bounded, and fully sanitized.
