# Task 28A-R3A-R2 Formal Gate Contract Repair and v3 Preflight

Generated: 2026-07-18T06:48:14Z

## Boundary

This task repaired only the formal-import gate contract and completed a new
read-only preflight. It did not execute a formal import, a backup, a schema
change, an Alembic operation, a vector rebuild, or a provider call.

## Gate Contract

- Contract version: `task28a_formal_gate_v2`
- QA status: `PASSED`
- Required QA boolean checks: `7`
- Static gate result: `PASSED`

## Read-only Preflight Result

- Status: `PREFLIGHT_V3_READY_AWAITING_APPROVAL`
- Formal database status: `PASSED`
- Formal documents / chunks: `372` / `4791`
- Test Huawei candidates / chunks: `10` / `937`
- New import candidates / estimated chunks: `10` / `937`
- Selected Sungrow / media / user cases: `0` / `0` / `0`
- Protected QA summary unchanged: `true`
- Baseline changed since v2: `false`

## Frozen v3 Plan

- Plan: `task28a_r3_formal_import_plan_v3.json`
- SHA-256: `00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- Required exact approval token: `APPROVE_TASK28A_R3_FORMAL_IMPORT:00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- Fresh full backup created: `false`
- Fresh full backup required before a separately authorized Apply: `true`

The preserved v1 and v2 plans remain historical evidence. The v2 token is
revoked for Apply because it binds the pre-repair importer hash.
