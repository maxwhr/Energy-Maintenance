# Task 22H Diagnosis / SOP / Task Agent Orchestration Report

## Scope

Task 22H adds three dedicated agent orchestrators for Huawei/Sungrow PV inverter maintenance workflows:

- `fault_diagnosis_agent`
- `sop_planner_agent`
- `task_orchestration_agent`

The implementation reuses the Agent Runtime, registered business tools, External API Provider Gateway, Multimodal Evidence Center, and existing service-layer modules. It does not add a migration, does not execute `alembic upgrade head`, does not call real external APIs, and does not create delivery packages.

## Runtime Dispatch

`AgentRuntimeService` now dispatches selected agent codes to dedicated orchestrators:

- `multimodal_evidence_agent` -> multimodal evidence orchestrator from Task 22G
- `fault_diagnosis_agent` -> fault diagnosis orchestrator
- `sop_planner_agent` -> SOP planner orchestrator
- `task_orchestration_agent` -> task orchestration orchestrator

Other agent codes continue to use the existing generic runtime path.

## Fault Diagnosis Agent

The `fault_diagnosis_agent` performs a traceable diagnosis-draft flow:

1. `validate_diagnosis_input`
2. `load_device_context`
3. `load_device_history`
4. `load_multimodal_evidence`
5. `retrieve_approved_knowledge`
6. `query_knowledge_graph`
7. `run_diagnosis_rules`
8. `run_safety_guard`
9. `build_diagnosis_summary`
10. `create_trace_links`
11. `finalize_diagnosis_agent_run`

Generated artifacts:

- `diagnosis_summary`
- `safety_checklist`
- `evidence_trace_summary`

The final answer explicitly states that the diagnosis is not a final repair conclusion and requires field review.

## SOP Planner Agent

The `sop_planner_agent` creates a structured SOP draft from the same PV inverter context:

1. `validate_sop_input`
2. `load_device_context`
3. `load_diagnosis_context`
4. `retrieve_sop_related_knowledge`
5. `query_sop_kg_context`
6. `generate_sop_draft`
7. `build_safety_checklist`
8. `create_sop_artifact`
9. `create_approval_request`
10. `finalize_sop_agent_run`

Generated artifacts:

- `sop_draft`
- `safety_checklist`
- `evidence_trace_summary`

The orchestrator creates an approval record with:

- `approval_type=sop_draft_review`
- `requested_action=review_sop_draft`
- `status=pending`

Approving the draft only updates the agent approval state. It does not create or execute a formal SOP record.

## Task Orchestration Agent

The `task_orchestration_agent` creates a maintenance task draft:

1. `validate_task_input`
2. `load_device_context`
3. `load_recent_history`
4. `build_task_draft`
5. `build_safety_requirement`
6. `create_task_artifact`
7. `create_approval_request`
8. `finalize_task_agent_run`

Generated artifacts:

- `task_draft`
- `safety_checklist`
- `evidence_trace_summary`

The orchestrator creates an approval record with:

- `approval_type=task_draft_review`
- `requested_action=review_task_draft`
- `status=pending`

The agent does not create a formal `maintenance_tasks` record and does not assign, start, complete, or cancel real maintenance tasks.

## Frontend

Task 22H adds `/agents/workbench` as the dedicated agent workbench.

The page supports:

- selecting the multimodal, diagnosis, SOP planner, or task orchestration agent;
- selecting PV inverter device and media evidence context;
- entering fault symptoms, alarm code, manufacturer, product series, and fault type;
- running dry-run agent workflows;
- showing run final answer, timeline, tool calls, artifacts, safety checklist, and approvals;
- rendering `diagnosis_summary`, `sop_draft`, and `task_draft` in business-readable panels;
- allowing expert/admin approval or rejection of pending draft approvals.

Viewer users can view where permitted but cannot create runs or approve/reject draft approvals.

## Safety Boundary

- No formal maintenance task is created automatically.
- No SOP execution is created automatically.
- No maintenance task status is changed automatically.
- No real mimo-2.5, cloud model, OCR API, local model, embedding, pgvector, Neo4j, Docker, or SQLite capability is introduced.
- Tool results are stored as traceable runtime records and artifacts.
- High-risk business actions remain draft plus human approval only.

## Verification Summary

Verified on the local Windows development environment with Energy-Maintenance backend on `http://127.0.0.1:8010` and PostgreSQL on `127.0.0.1:55432`.

Passed checks:

- `uv run python -m compileall app`
- `uv run python -m alembic -c alembic.ini current`
- `uv run python scripts\check_diagnosis_sop_task_agent_flow.py`
- `uv run python scripts\check_multimodal_evidence_agent_flow.py`
- `uv run python scripts\check_multimodal_adapter_contract.py`
- `uv run python scripts\check_multimodal_evidence_flow.py`
- `uv run python scripts\check_external_api_gateway_flow.py`
- `uv run python scripts\check_agent_business_tools_flow.py`
- `npm.cmd install`
- `npm.cmd audit`
- `npm.cmd run build`
- `backend\scripts\build_and_install_frontend.ps1`
- `node backend\scripts\check_task22h_diagnosis_sop_task_agent_browser.mjs`
- `scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`

Known local notes:

- Port `8000` and PostgreSQL port `5432` are occupied by other local projects; this task used `8010` and `55432`.
- Real provider credentials are still not configured, so external model/OCR behavior remains blocked or dry-run only.
- Production conversion from approved drafts to formal SOP templates, SOP executions, or maintenance tasks remains a future task.

## Follow-up Boundary for Task 22I

Task 22I builds on the diagnosis, SOP, and task orchestration artifacts by adding a `knowledge_curator_agent`.

The 22I curator consumes source Agent Runs and Artifacts from the 22H flows, plus media evidence, device history, existing knowledge search results, knowledge graph context, engineer notes, and safety-guard output.

The curator only creates draft Agent Artifacts and one pending approval:

- `maintenance_case_summary`
- `knowledge_contribution_draft`
- `kg_candidate_suggestion`
- `safety_checklist`
- `evidence_trace_summary`
- `approval_type=knowledge_contribution_draft_review`

The curator does not create formal knowledge contributions, documents, chunks, or knowledge-graph records. Formal conversion remains reserved for Task 22J.
