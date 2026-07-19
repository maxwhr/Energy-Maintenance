# Task 28A-R3A Formal Import Preflight

Generated: 2026-07-18T05:28:24Z

## Boundary

This is a dry-run only preflight. The formal database connection was not
established; no formal SQL statement, write, migration, backup creation, or
importer Apply path was executed.

## Result

- Preflight status: `BLOCKED_FORMAL_DATABASE_UNREACHABLE`
- Test Huawei candidates: `10`
- Valid test Huawei candidates: `10`
- Verified test Huawei chunks: `937`
- Formal database status: `BLOCKED_FORMAL_DATABASE_UNREACHABLE`
- Formal target: `127.0.0.1:55432 / energy_maintenance / energy_user`
- Formal identity, Alembic revision, schema comparison, duplicate comparison,
  protected QA-record readback, and transaction-read-only confirmation: not
  executed because the target did not accept a connection.
- Candidate comparison result: `FORMAL_COMPARISON_NOT_EXECUTED` for all `10`
  candidates; no candidate is approved for import while duplicate checks are unavailable.
- Formal write operations: `0`
- Selected Sungrow documents: `0`
- Selected media and fault-case annotations: `0`
- Fresh full backup created: `false`
- Fresh full backup required before Apply: `true`
- Protected-file baseline unchanged after preflight: `true`

## Frozen Plan

- Plan: `task28a_r3_formal_import_plan.json`
- SHA-256: `5e803262a30276a78f21ba39f5a77553dc5099250b27d826c59b6771c5ba9f55`
- Required exact approval token: `not issued while preflight is blocked`

Any later Apply must use a fresh PostgreSQL `pg_dump -Fc` backup, revalidate
the plan SHA-256 and protected-file baseline, and be separately authorized.

## Task 28A-R3A-R1 Reachability Recovery and v2 Rerun

The original R3A blocked result above remains preserved as historical evidence.
R3A-R1 used only a temporary `pg_ctl` process for the data directory declared
by the existing Windows service metadata; the service itself remained
`Stopped` and `Disabled` and was not modified.

- Formal database identity, Alembic `20260712_0015`, and SQLAlchemy schema
  coverage passed under `BEGIN TRANSACTION READ ONLY`.
- The explicit temporary-table write probe was rejected by PostgreSQL and
  rolled back. Formal business SQL writes, schema changes, imports, reviews,
  vectors, migrations, and backups all remained `0`.
- The protected QA record was found and its redacted digest was unchanged on a
  second read. The current `qa_records` schema does not persist `request_id` or
  `status`; that limitation is recorded without changing the schema.
- All 10 Huawei candidates (937 test chunks) were compared to the formal
  catalog. They are `NEW_IMPORT_CANDIDATE`, with zero metadata conflicts,
  same-title/different-hash conflicts, or invalid candidates.
- Sungrow selection, media selection, and user-case/fault-case selection all
  remain `0`.
- V2 status: `PREFLIGHT_READY_AWAITING_APPROVAL`.
- V2 plan SHA-256:
  `200d21ed461ebd9c22d8adbb966b1504ff6ec8714efa4005ef6d0c772bfa0a20`.
- The v1 SHA-256 remains
  `5e803262a30276a78f21ba39f5a77553dc5099250b27d826c59b6771c5ba9f55`.

No Apply was executed. A separate R3B task still requires the exact v2
approval token, a fresh `pg_dump -Fc` backup, and baseline revalidation.

## Task 28A-R3A-R2 Gate Contract Repair and v3 Preflight

- Status: `PREFLIGHT_V3_READY_AWAITING_APPROVAL`
- Mode: static gate validation plus formal/test PostgreSQL read-only preflight only.
- Formal database business writes, schema changes, backup creation, and Apply: `0`.
- Frozen v3 plan SHA-256: `00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- Required exact v3 approval token: `APPROVE_TASK28A_R3_FORMAL_IMPORT:00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- The v2 token is historical evidence only and is revoked for Apply.
- A fresh `pg_dump -Fc` backup remains required before any separately authorized Apply.
