# Task 28A Project-local PostgreSQL Test Cluster

## Historical Gate and R2C Resolution

Task 28A-R2B correctly stopped when `Get-Command` did not expose `initdb.exe`, `pg_ctl.exe`, `psql.exe`, or `createdb.exe`. Task 28A-R2C was explicitly authorized to inspect existing Windows service metadata and its executable directory. No service was started, stopped, enabled, disabled, or reconfigured.

The service metadata identified a complete PostgreSQL 16.14 binary set at:

`D:\Work Space\PostgreSQL\bin`

The same directory contained `initdb.exe`, `pg_ctl.exe`, `psql.exe`, `createdb.exe`, `postgres.exe`, and `pg_isready.exe`, all reporting version 16.14.

## Isolated Cluster Result

- Data path: `.runtime/task28a/postgres/data`
- Log path: `.runtime/task28a/postgres/logs`
- Port: `127.0.0.1:55433`
- Administrator role: `task28a_cluster_admin`
- Encoding: UTF8
- Authentication: SCRAM-SHA-256
- Start / stop / restart / readiness: passed
- Final state: stopped; `55433` is non-listening

The required fixed-path scripts were created under `backend/scripts`:

- `start_task28a_postgres.ps1`
- `stop_task28a_postgres.ps1`
- `check_task28a_postgres.ps1`

They accept no arbitrary data-directory parameter and perform no Windows service operation.

## Isolation Confirmation

- Existing `127.0.0.1:55432` PostgreSQL instance: not operated.
- Formal database `energy_maintenance`: no read/write/migration performed.
- Application role `energy_user`: not modified.
- Test role/database: created only within the project-local 55433 cluster.
- Temporary initialization password file: deleted before final validation and not retained.
- Administrator URL and test `DATABASE_URL`: process-scoped only and cleared after commands.

See `42_postgresql_binary_discovery_and_resume.md` for complete Task 28A-R2C evidence.
