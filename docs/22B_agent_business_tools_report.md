# Task 22B Agent Business Tools Report

## Scope

Task 22B connects the agent runtime to existing backend business services through a controlled tool execution layer.

This task does not introduce a new database migration, packaging step, external model call, OCR runtime, embedding, pgvector, Docker route, or SQLite fallback.

## Implemented Tool Layer

New backend service package:

```text
backend/app/services/agent_tools/
```

Registered tool adapters:

```text
knowledge_search
kg_business_context
device_lookup
device_history
media_lookup
media_ocr
media_mimo_analysis
diagnosis_rule_engine
sop_generator
task_draft_creator
knowledge_contribution_draft_creator
record_center_lookup
safety_guard
model_gateway_chat
correction_submitter
human_approval
```

Tool execution is coordinated by:

```text
backend/app/services/agent_tool_executor.py
```

Each tool call creates or updates agent runtime records for steps, tool calls, artifacts, approvals, and events. No new tables were added in Task 22B.

## Business Boundaries

- `knowledge_search` uses the existing retrieval service and saves normal QA records through that service.
- `diagnosis_rule_engine` uses the existing diagnosis service and saves normal diagnosis records through that service.
- `sop_generator` generates SOP draft content through the existing SOP service.
- `model_gateway_chat` uses `rule_based` by default and does not require cloud or local model configuration.
- `media_ocr` returns existing OCR text when present; otherwise it reports blocked if OCR is disabled.
- `media_mimo_analysis` is blocked and does not call any external mimo-2.5 API.
- `task_draft_creator`, `knowledge_contribution_draft_creator`, `correction_submitter`, and `human_approval` are approval-gated and create draft artifacts only.

## API Changes

Enhanced:

```text
POST /api/agents/runs
```

The request can include `tool_names` or `tools`, plus optional `media_ids` and `tool_inputs`.

Added:

```text
POST /api/agents/runs/{run_id}/execute-tool
```

This endpoint is restricted to `admin`, `expert`, and `engineer`. Viewer users are blocked.

## Verification

Task 22B verification command:

```powershell
cd backend
uv run python scripts\check_agent_business_tools_flow.py
```

Do not run `alembic upgrade head` for Task 22B.

## Known Limits

- No real mimo-2.5 service is connected.
- No real OCR execution is required.
- No cloud model or local GGUF model is required.
- No embedding or pgvector retrieval is used.
- High-risk tools are draft-only until human approval.

## Next Boundary

- Task 22C can continue with the multimodal evidence center data/service layer.
- Task 22D can implement the real mimo-2.5 adapter only after explicit configuration and approval.
- A full agent frontend workbench remains deferred; Task 22B only updates frontend types and API wrappers.
- Packaging remains prohibited until the user explicitly says to start packaging.

## Task 22C Follow-up Compatibility Note

Task 22C adds an External API Provider Gateway used by agent tools that depend on future external providers.

The following Task 22B tools remain compatible:

- `media_mimo_analysis`: now reads the `mimo_2_5` provider route and remains blocked when no external configuration is available.
- `media_ocr`: now reads the OCR provider route and returns existing OCR context first; otherwise it remains blocked.
- `model_gateway_chat`: keeps the existing model gateway behavior and additionally records external provider route dry-run status.

`check_agent_business_tools_flow.py` passed after the Task 22C changes.

## Task 22D Follow-up Compatibility Note

Task 22D adds a multimodal evidence center. Agent media tools remain compatible:

- `media_lookup` includes compact multimodal summary metadata.
- `media_ocr` reads latest succeeded OCR result records before returning provider blocked status.
- `media_mimo_analysis` reads accepted or pending AI analysis records before returning provider blocked status.

`check_agent_business_tools_flow.py` passed after the Task 22D changes.
