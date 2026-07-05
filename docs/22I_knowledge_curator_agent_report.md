# Task 22I Knowledge Curator Agent Report

## Summary

Task 22I adds `knowledge_curator_agent`, a draft-only knowledge curation workflow for Huawei/Sungrow PV inverter maintenance experience.

The agent consolidates diagnosis, SOP, task, multimodal evidence, engineer notes, device history, existing knowledge, graph context, and safety guard output into reviewable Agent Artifacts.

This task does not create formal knowledge-base content and does not package delivery artifacts.

## Orchestrator

The new orchestrator is:

```text
backend/app/services/agent_orchestrators/knowledge_curator_orchestrator.py
```

It is dispatched by `AgentRuntimeService` when:

```text
agent_code=knowledge_curator_agent
```

Required workflow steps:

- `validate_curator_input`
- `load_device_context`
- `load_device_history`
- `load_source_agent_artifacts`
- `load_media_evidence`
- `search_existing_knowledge`
- `query_kg_context`
- `run_safety_guard`
- `build_maintenance_case_summary`
- `build_knowledge_contribution_draft`
- `build_kg_candidate_suggestion`
- `create_approval_request`
- `create_evidence_trace`
- `finalize_curator_run`

Additional supporting steps:

- `load_record_center_context`
- `prepare_human_approval`

Default tools:

- `device_lookup`
- `device_history`
- `record_center_lookup`
- `knowledge_search`
- `kg_business_context`
- `media_lookup`
- `safety_guard`
- `knowledge_contribution_draft_creator`
- `human_approval`

## Generated Artifacts

The curator creates these Agent Artifacts:

- `maintenance_case_summary`
- `knowledge_contribution_draft`
- `kg_candidate_suggestion`
- `safety_checklist`
- `evidence_trace_summary`

The artifacts include source-trace, duplicate-risk, mocked-evidence, unreviewed-AI-evidence, limitation, and safety boundary information where available.

## Approval Boundary

The orchestrator creates one pending approval:

```text
approval_type=knowledge_contribution_draft_review
requested_action=review_knowledge_contribution_draft
```

Approval payload includes:

```text
can_convert_to_formal_contribution=false
conversion_task=Task 22J
formal_contribution_created=false
formal_document_created=false
approved_chunks_created=false
formal_kg_records_created=false
```

Approving or rejecting the approval only updates `agent_approvals`.

## Frontend

The `/agents/workbench` page now supports `knowledge_curator_agent`.

Added interactions:

- agent selector option for knowledge curation;
- engineer notes input;
- source Agent Run ID input;
- source Artifact ID input;
- five business-readable artifact panels;
- approval panel integration for expert/admin review.

Viewer users remain read-only. Engineer users can create dry-run curator runs. Expert/admin users can review draft approvals.

## Safety Boundary

Task 22I does not:

- create formal `knowledge_contributions`;
- create formal `knowledge_documents`;
- create formal `knowledge_chunks`;
- create formal knowledge-graph nodes or edges;
- call real external APIs;
- enable real OCR;
- introduce embedding, pgvector, Neo4j, Docker, or SQLite;
- generate delivery zip files or delivery staging artifacts.

Formal conversion from approved draft artifacts is reserved for Task 22J.

## Verification Summary

Verified on the local Windows development environment with Energy-Maintenance backend on `http://127.0.0.1:8010` and PostgreSQL on `127.0.0.1:55432`.

Passed checks:

- `uv run python -m compileall app scripts`
- `uv run python -m alembic -c alembic.ini current`
- `uv run python scripts\seed_agent_runtime.py`
- `uv run python scripts\seed_external_api_providers.py`
- `uv run python scripts\check_knowledge_curator_agent_flow.py`
- `uv run python scripts\check_diagnosis_sop_task_agent_flow.py`
- `uv run python scripts\check_multimodal_evidence_agent_flow.py`
- `uv run python scripts\check_multimodal_adapter_contract.py`
- `uv run python scripts\check_multimodal_evidence_flow.py`
- `uv run python scripts\check_external_api_gateway_flow.py`
- `uv run python scripts\check_agent_business_tools_flow.py`
- `npm.cmd audit`
- `npm.cmd run build`
- `backend\scripts\build_and_install_frontend.ps1`
- `node backend\scripts\check_task22i_knowledge_curator_agent_browser.mjs`
- `scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`

Browser verification created a real curator run through the frontend, displayed the required artifacts, reviewed an approval, verified viewer blocking, and detected no blocking console or network errors.

## Known Local Notes

- Port `8000` and PostgreSQL port `5432` are occupied by other local projects; this task used `8010` and `55432`.
- Real provider credentials are still not configured, so external model/OCR behavior remains blocked or dry-run only.
- Formal draft conversion is implemented by Task 22J and remains explicit/manual rather than automatic on approval.

## Next Task

Task 22J implements controlled conversion from approved draft artifacts into formal business objects. Future work may add richer conversion history UI or a second-stage review workflow, but packaging still requires explicit user instruction.
