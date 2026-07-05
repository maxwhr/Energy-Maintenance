# Task 22J Agent Artifact Conversion Report

## Summary

Task 22J adds controlled conversion from approved Agent draft artifacts into formal business objects for Huawei/Sungrow PV inverter maintenance workflows.

The task keeps the existing public `/api` prefix, does not add a database migration, and does not generate delivery packages.

## Conversion Targets

Supported conversions:

- `knowledge_contribution_draft` -> `knowledge_contributions`
- `sop_draft` -> `sop_templates`
- `task_draft` -> `maintenance_tasks`
- `kg_candidate_suggestion` -> `kg_candidates` through a new `kg_extraction_runs` record

Approval alone does not perform conversion. Expert/admin users must explicitly call the conversion API or click the conversion action in the Agent Workbench.

## Persistence Design

No new table is introduced in Task 22J.

Conversion audit is stored in `agent_event_logs` with:

```text
event_type=draft_converted_to_formal_object
```

The event payload stores:

- `source_artifact_id`
- `source_artifact_type`
- `source_agent_run_id`
- `approval_id`
- `target_type`
- `target_id`
- `conversion_trace_id`
- `converted_by`
- `converted_at`
- `warnings`
- `created_records`

Duplicate conversion of the same `source_artifact_id + target_type` is blocked by checking existing conversion events.

## API

New Agent conversion APIs:

```text
GET  /api/agents/artifacts/{artifact_id}/conversion-status
POST /api/agents/artifacts/{artifact_id}/convert
GET  /api/agents/conversions
GET  /api/agents/conversions/{conversion_trace_id}
```

`POST /api/agents/artifacts/{artifact_id}/convert` accepts:

```json
{
  "target_type": "knowledge_contribution",
  "approval_id": "uuid",
  "override_warnings": false,
  "comment": "manual conversion note"
}
```

Allowed `target_type` values:

- `knowledge_contribution`
- `sop_template`
- `maintenance_task`
- `kg_candidate`

## Role Boundary

- `viewer`: can read allowed conversion status/list summaries but cannot convert.
- `engineer`: can create draft agent runs but cannot convert.
- `expert`: can convert approved non-risky drafts.
- `admin`: can convert approved drafts and may use `override_warnings` for mocked or unreviewed evidence.

Rejected, cancelled, missing, or non-approved approvals are blocked.

## Business Boundaries

The conversion layer is intentionally conservative:

- Knowledge contribution conversion creates a `knowledge_contributions` row with `review_status=pending_review`.
- It does not create `knowledge_documents`.
- It does not create `knowledge_chunks`.
- SOP conversion creates a `sop_templates` row with `status=draft`.
- It does not create SOP execution records.
- Task conversion creates a `maintenance_tasks` row with `status=pending` and `task_status=pending`.
- It does not start or complete the task.
- It does not create a `device_maintenance_records` row.
- KG conversion creates `kg_extraction_runs` and pending `kg_candidates`.
- It does not create formal `kg_nodes` or `kg_edges`.

## Frontend

The `/agents/workbench` page now displays a draft conversion panel when convertible artifacts are present.

The panel:

- shows target conversion type;
- shows approval status;
- disables conversion before approval;
- hides conversion buttons from viewer/engineer users;
- shows converted target IDs and `conversion_trace_id`;
- requires admin override for mocked or unreviewed evidence.

## Verification Scripts

Added:

```text
backend/scripts/check_agent_artifact_conversion_flow.py
backend/scripts/check_task22j_artifact_conversion_browser.mjs
```

The scripts verify approval boundaries, duplicate conversion blocking, role blocking, target table deltas, UI conversion buttons, browser runtime errors, and no delivery package generation.

## Explicit Non-goals

Task 22J does not:

- call real external APIs;
- enable real OCR;
- introduce embedding, pgvector, Neo4j, Docker, or SQLite;
- create delivery zip files;
- delete formal data or uploaded files;
- auto-convert draft artifacts on approval.

## Next Task

Task 24E later added the dedicated `agent_artifact_conversions` audit table, conversion history APIs, frontend conversion history display, and concurrent duplicate-prevention checks. Packaging must still wait until the user explicitly says "开始打包".
