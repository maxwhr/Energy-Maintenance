# Task 22A Agent Runtime Foundation Report

## Scope

Task 22A adds the backend foundation for an Agent Runtime and Tool Registry for Energy-Maintenance.

This task is limited to:

- agent definitions
- tool registry metadata
- agent runs
- agent steps
- tool-call logs
- human approvals
- agent artifacts
- agent event logs
- rule-based demo / dry-run execution mode

This task does not connect the real `mimo-2.5` API, does not call external model services, does not introduce OCR execution as a required capability, and does not add pgvector or embedding.

## Database

Migration:

```text
backend/alembic/versions/20260601_0004_add_agent_runtime_tables.py
```

Down revision:

```text
20260601_0003
```

New tables:

- `agent_definitions`
- `agent_tools`
- `agent_runs`
- `agent_steps`
- `agent_tool_calls`
- `agent_approvals`
- `agent_artifacts`
- `agent_event_logs`

## Backend Files

- `backend/app/models/agent.py`
- `backend/app/schemas/agent.py`
- `backend/app/repositories/agent_repository.py`
- `backend/app/services/agent_runtime_service.py`
- `backend/app/services/agent_tool_registry.py`
- `backend/app/services/agent_approval_service.py`
- `backend/app/api/routes/agents.py`
- `backend/scripts/seed_agent_runtime.py`
- `backend/scripts/check_agent_runtime_flow.py`

Updated registration files:

- `backend/app/main.py`
- `backend/app/models/__init__.py`
- `backend/app/repositories/__init__.py`
- `backend/app/services/__init__.py`

## API

New public prefix:

```text
/api/agents
```

Endpoints:

- `GET /api/agents/definitions`
- `GET /api/agents/definitions/{agent_code}`
- `GET /api/agents/tools`
- `GET /api/agents/runs`
- `POST /api/agents/runs`
- `GET /api/agents/runs/{run_id}`
- `POST /api/agents/runs/{run_id}/cancel`
- `GET /api/agents/runs/{run_id}/steps`
- `GET /api/agents/runs/{run_id}/tool-calls`
- `GET /api/agents/runs/{run_id}/approvals`
- `POST /api/agents/approvals/{approval_id}/approve`
- `POST /api/agents/approvals/{approval_id}/reject`
- `GET /api/agents/runs/{run_id}/artifacts`
- `GET /api/agents/events`

## Seed Data

`backend/scripts/seed_agent_runtime.py` idempotently creates:

Agent definitions:

- `multimodal_evidence_agent`
- `retrieval_qa_agent`
- `fault_diagnosis_agent`
- `sop_planner_agent`
- `task_orchestration_agent`
- `knowledge_curator_agent`
- `safety_guard_agent`

Tool registry entries:

- `knowledge_search`
- `kg_business_context`
- `media_lookup`
- `media_ocr`
- `media_mimo_analysis`
- `device_lookup`
- `device_history`
- `diagnosis_rule_engine`
- `sop_generator`
- `task_draft_creator`
- `knowledge_contribution_draft_creator`
- `record_center_lookup`
- `correction_submitter`
- `safety_guard`
- `human_approval`
- `model_gateway_chat`

`media_mimo_analysis` is seeded as:

```text
enabled=false
metadata_json.requires_external_config=true
metadata_json.provider=mimo-2.5
metadata_json.status=blocked
```

## Permissions

- `viewer`: may read definitions, tools, and allowed runs; may not create runs or approve/reject approvals.
- `engineer`: may create dry-run agent runs; may read own runs; may not approve high-risk actions.
- `expert`: may create runs and approve/reject approvals.
- `admin`: full Agent Runtime access.

## Boundaries

- Agent tools do not bypass RBAC.
- Agent Runtime does not call repository/model directly from API handlers.
- Agent Runtime records run, step, tool-call, approval, artifact, and event traces.
- High-risk or approval-required tools create pending approvals.
- The current task does not execute real dangerous write actions.
- The current task does not connect `mimo-2.5`.
- No delivery package is generated in Task 22A.

## Next Step

Task 22B should connect selected agent tools to existing business services through a service-layer adapter, not directly to repositories.
# Task 22B Follow-up Note

Task 22B builds on the Task 22A runtime foundation by connecting the registered tool metadata to actual backend service adapters.

The runtime now executes registered business tools, records tool calls, creates draft artifacts, and creates approval records for high-risk draft actions.

Task 22B still does not connect mimo-2.5, cloud models, local GGUF models, OCR execution, embedding, pgvector, Docker, or SQLite.

Detailed report: `docs/22B_agent_business_tools_report.md`.

---
