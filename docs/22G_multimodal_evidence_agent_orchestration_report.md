# Task 22G Multimodal Evidence Agent Orchestration Report

## Scope

Task 22G adds deep orchestration for `multimodal_evidence_agent` in the Huawei/Sungrow PV inverter maintenance system.

The implementation reuses the Agent Runtime, External API Provider Gateway, and Multimodal Evidence Center created in Tasks 22A-22F. It does not add a migration and does not call real external APIs.

## Orchestration Flow

`POST /api/agents/runs` routes to the dedicated multimodal evidence orchestrator when:

```json
{
  "agent_code": "multimodal_evidence_agent"
}
```

The fixed step chain is:

1. `validate_input`
2. `load_media_context`
3. `run_ocr_evidence`
4. `run_visual_analysis`
5. `run_safety_guard`
6. `build_evidence_summary`
7. `create_evidence_links`
8. `finalize_run`

Each step records status, input/output summaries, and `reasoning_summary` in `agent_steps`.

## Tool Behavior

- `media_lookup`: reads selected media metadata and existing multimodal evidence summary.
- `media_ocr`: reads existing OCR results; when `mock_run=true`, writes mocked OCR results; otherwise returns blocked if OCR providers are not configured.
- `media_mimo_analysis`: reads accepted or mocked analysis; when `mock_run=true`, writes mocked AI analysis; otherwise returns blocked if mimo/vision providers are not configured.
- `safety_guard`: generates a conservative PV inverter safety checklist locally without external API calls.

Blocked OCR or visual analysis tools do not crash the run. The final answer explicitly states blocked and mocked boundaries.

## Artifacts

Every orchestrated run creates at least:

- `multimodal_evidence_summary`
- `safety_checklist`
- `evidence_trace_summary`

The artifacts include media ids, OCR/visual status, suggested next steps, limitations, mocked/dry-run flags, evidence link ids, and human review requirements.

## Evidence Links

The orchestrator creates `media_evidence_links` for:

- `source_type=agent_run`, `relation_type=used_as_context`
- `source_type=agent_artifact`, `relation_type=generated_from`

This links media evidence back to the agent run and generated artifacts.

## API

Task 22G reuses:

```text
POST /api/agents/runs
```

It also adds:

```text
GET /api/agents/runs/{run_id}/timeline
```

The timeline endpoint returns:

- run
- steps
- tool_calls
- artifacts
- approvals
- events

## Frontend

The `/multimodal` page now supports:

- selected media context
- site description input
- default tool chain selection
- dry-run toggle
- mock-run toggle
- dedicated "create multimodal evidence agent run" action
- run result and final answer
- timeline
- tool calls
- evidence summary
- safety checklist
- artifact and trace summary

Viewer users cannot create runs. Engineer users can create dry-run runs. Expert/admin users can create mock-run runs.

## Safety Boundary

No real mimo-2.5, cloud vision, OCR API, local model, pgvector, embedding, Neo4j, Docker, or SQLite capability is introduced.

Mocked results are local contract-test evidence only and must not be used as production machine recognition output.

## Task 22H Regression Note

Task 22H keeps `multimodal_evidence_agent` on the Task 22G dedicated orchestrator path.

Regression checks confirmed:

- multimodal evidence agent dry-run and mock-run still work;
- required 22G artifacts are still generated;
- timeline, tool calls, approvals, and evidence links remain readable;
- no real external OCR or visual model API is called;
- the new diagnosis, SOP, and task agent dispatch does not replace or bypass the 22G flow.
