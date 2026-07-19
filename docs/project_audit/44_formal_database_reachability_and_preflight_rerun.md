# Task 28A-R3A-R1 Formal Database Reachability and Preflight Rerun

Generated: 2026-07-18

## Scope and Boundary

This rerun temporarily started only the PostgreSQL 16 cluster named by the
existing `postgresql-x64-16` Windows service metadata. The Windows service
remained `Stopped` and `Disabled`; it was not started, reconfigured, or
registered. The task used `pg_ctl` with the service-declared data directory,
bound only to `127.0.0.1:55432`.

The formal session set `default_transaction_read_only=on`, a 30-second
statement timeout, a 5-second lock timeout, and a 60-second idle transaction
timeout before entering `BEGIN TRANSACTION READ ONLY`. No formal import,
migration, approval, review, vector operation, backup, or business-table DML
was executed.

## Formal Read-Only Evidence

- Database identity: `energy_maintenance` / `energy_user` on `127.0.0.1:55432`.
- Formal Alembic revision: `20260712_0015`, matching the required head.
- SQLAlchemy model tables missing from the formal schema: `0`.
- The only formal schema table outside SQLAlchemy metadata is Alembic's own
  `alembic_version` bookkeeping table.
- The write-protection probe `CREATE TEMP TABLE task28a_readonly_probe(...)`
  was rejected by PostgreSQL with `ReadOnlySqlTransaction` and rolled back.
- Formal business SQL writes: `0`; schema changes: `0`; import writes: `0`.

## Protected Record and Baseline

- Protected QA record ID and trace ID were found and its redacted digest was
  unchanged when read again after the preflight.
- The current `qa_records` schema has no `request_id` or `status` column.
  The required request identifier is retained as task evidence, but cannot be
  independently verified from that table without a separately authorized
  schema/application change. This task made no such change.
- Fresh full backup created: `false`.
- Fresh `pg_dump -Fc` backup required before any future Apply: `true`.

## Candidate Comparison

- Test Huawei candidates: `10`.
- Verified test Huawei chunks: `937`.
- Formal baseline: `372` knowledge documents and `4,791` knowledge chunks.
- Classifications: `10` `NEW_IMPORT_CANDIDATE`; `0` metadata conflicts;
  `0` same-title/different-hash conflicts; `0` invalid candidates.
- Selected Sungrow documents: `0`; excluded future-Sungrow documents: `10`.
- Selected media assets: `0`; excluded media assets: `144`.
- Selected fault-case/user-case annotations: `0`; excluded annotations: `2`.

## Immutable Plan

- Preserved v1 blocked plan SHA-256:
  `5e803262a30276a78f21ba39f5a77553dc5099250b27d826c59b6771c5ba9f55`.
- New v2 plan: `task28a_r3_formal_import_plan_v2.json`.
- New v2 plan SHA-256:
  `200d21ed461ebd9c22d8adbb966b1504ff6ec8714efa4005ef6d0c772bfa0a20`.
- V2 status: `PREFLIGHT_READY_AWAITING_APPROVAL`.
- Its exact approval token is stored only in the v2 SHA-256 sidecar and binds
  to the v2 plan hash. It authorizes no action by itself.

## Required Before Any Apply

1. Receive a separate explicit Apply authorization using the exact v2 token.
2. Revalidate the plan SHA-256 and protected baseline.
3. Create a fresh full `pg_dump -Fc` backup of the formal database.
4. Revalidate the formal baseline and conflict classification.
5. Execute a separately reviewed R3B Apply task only.

## Teardown and Restoration

- The project-local test cluster was stopped and `55433` was confirmed free.
- The formal instance started by this task was stopped with `pg_ctl -m fast`
  and `55432` was confirmed free.
- `postgresql-x64-16` remains `Stopped` with startup mode `Disabled`.
- The service configuration was not modified.
- Runtime startup log:
  `.runtime/task28a-r3-r1/logs/formal_postgres_start.log`.

## Task 28A-R3A-R2 Gate Contract Repair and v3 Preflight

- Status: `PREFLIGHT_V3_READY_AWAITING_APPROVAL`
- Mode: static gate validation plus formal/test PostgreSQL read-only preflight only.
- Formal database business writes, schema changes, backup creation, and Apply: `0`.
- Frozen v3 plan SHA-256: `00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- Required exact v3 approval token: `APPROVE_TASK28A_R3_FORMAL_IMPORT:00932bbb44ce7088fbd301e220a15f5ed02383c8b1b62aa23a5b7edef0fc7d8c`
- The v2 token is historical evidence only and is revoked for Apply.
- A fresh `pg_dump -Fc` backup remains required before any separately authorized Apply.
