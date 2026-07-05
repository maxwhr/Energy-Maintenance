# Task 24E Agent Conversion Concurrency and Audit Report

## Scope

Task 24E adds a formal audit table for agent draft-to-business-object conversion and hardens the conversion workflow against duplicate and concurrent requests.

This task does not package the project, does not create delivery archives, does not introduce external model calls, and does not delete existing business data.

## Implemented Design

- Added `agent_artifact_conversions` as the primary conversion audit source.
- Kept `agent_event_logs` as a supplementary compatibility record.
- Added a database unique constraint on `(source_artifact_id, target_type)`.
- Added row-level artifact locking before conversion execution.
- Kept approval and conversion as separate actions.
- Required `expert` or `admin` for conversion.
- Blocked viewer, engineer, pending approval, rejected approval, missing approval, and unsupported artifact types.
- Recorded failed conversions with `conversion_status=failed` and sanitized `error_message`.
- Added conversion history APIs for run-level and artifact-level lookup.
- Added frontend conversion history display with `conversion_trace_id`, status, target id, timestamps, and failure reason.

## Database

Migration:

```text
backend/alembic/versions/20260601_0008_add_agent_artifact_conversions.py
```

Down revision:

```text
20260601_0007
```

New table:

```text
agent_artifact_conversions
```

Important constraints and indexes:

- `uq_agent_artifact_conversions_artifact_target`
- `ix_agent_artifact_conversions_source_run_id`
- `ix_agent_artifact_conversions_source_artifact_id`
- `ix_agent_artifact_conversions_conversion_trace_id`
- `ix_agent_artifact_conversions_conversion_status`
- `ix_agent_artifact_conversions_target_type`
- `ix_agent_artifact_conversions_target_id`

## API

New or strengthened endpoints:

```text
GET  /api/agents/artifacts/{artifact_id}/conversion-status
POST /api/agents/artifacts/{artifact_id}/convert
GET  /api/agents/conversions
GET  /api/agents/conversions/{conversion_trace_id}
GET  /api/agents/conversions/{conversion_id}/detail
POST /api/agents/conversions/{conversion_id}/void
GET  /api/agents/runs/{run_id}/conversions
GET  /api/agents/artifacts/{artifact_id}/conversions
```

The void endpoint is intentionally reserved and does not delete or roll back formal business records.

## Verification Coverage

Added:

```text
backend/scripts/check_agent_conversion_concurrency_flow.py
backend/scripts/check_task24e_conversion_history_browser.mjs
```

Enhanced:

```text
backend/scripts/check_agent_artifact_conversion_flow.py
```

Expected checks:

- one concurrent conversion creates exactly one formal object;
- duplicate calls return already-converted or conflict/in-progress semantics;
- conversion history is queryable by artifact and run;
- failed target creation leaves a failed conversion record;
- event log compatibility record is still written;
- viewer and engineer cannot convert;
- browser UI shows conversion history and hides duplicate convert action;
- no package or delivery archive is generated.

## Boundaries

Task 24E does not:

- enable real MIMO, OCR, Cloud LLM, local model, embedding, pgvector, or Neo4j;
- package the project;
- create delivery zip files;
- remove old audit data;
- hard-delete artifacts or uploaded media;
- roll back formal business objects after conversion.

