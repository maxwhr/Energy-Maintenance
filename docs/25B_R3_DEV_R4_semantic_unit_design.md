# Task 25B-R3-DEV-R4 Semantic Unit Design

## Boundary

R4 keeps `energy_kn_te_v4_1024_v1` and writes only the isolated `pilot_r4_grounded` partition. `pilot_r2`, `pilot_r3_semantic`, the default partition, document approvals, original 1,262 vectors, and `expert_verified` are immutable.

## Source model

`MaintenanceSemanticUnitService` deterministically groups directly supporting adjacent chunks into a stable unit ID derived from document, section path, unit type, and source hash. Each unit retains its original chunk IDs, pages, section locator, source hash, representation version, language, approval mode, current-version flag, and engineering quality state.

Only `ENGINEERING_VERIFIED_SOURCE_GROUNDED` units enter the R4 index. Marketing/front matter, short low-signal sections, missing locators, non-Chinese content, non-current content, and unapproved content are excluded.

## Unit and anchor semantics

Supported types are ALARM, SYMPTOM, CAUSE, ACTION, PROCEDURE, SAFETY, PREREQUISITE, VERIFICATION, COMPONENT, COMMUNICATION, and FULL_SECTION. Alarm and procedure units retain source-bounded cause/action and prerequisite/action/verification context rather than promoting isolated steps to complete answers.

Each unit can produce multiple typed anchors. Typed representations contain only source-derived intent fields plus a short source-evidence fragment; they do not contain benchmark queries, expected IDs, test data, or inferred facts. Retrieval selects no more than three anchor types, executes independent type-filtered searches, merges hits by semantic unit, and maps the final result back to original chunks and pages. Canonical retrieval text is never citation evidence.

## Persistence

The existing `maintenance_semantic_anchors` table and JSONB mapping persist unit fields and multiple source chunk IDs. No migration was needed; Alembic remains `20260712_0012`.

## Current build

- Documents: 16
- Active source chunks considered: 1,262
- Semantic units: 390
- Typed anchors: 1,289
- Unit type counts: ACTION 2, ALARM 150, CAUSE 8, COMMUNICATION 134, COMPONENT 1, PROCEDURE 51, SAFETY 41, SYMPTOM 3
- Quality gate: passed
- Expert verification claimed: no

Evidence: `.runtime/task25b_r3_dev_r4/semantic_units.json`, `semantic_unit_manifest.json`, and `semantic_unit_quality.json`.

