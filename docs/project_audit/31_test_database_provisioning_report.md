# Task 28A Test Database Provisioning Report

## Result

- Status: `PROVISIONED_AND_MIGRATED`
- Isolated cluster: `127.0.0.1:55433`
- Test role: `energy_maintenance_test_user`
- Test database: `energy_maintenance_task27a_test`
- Database owner: `energy_maintenance_test_user`, verified by the guarded provisioner
- Alembic revision: `20260712_0015 (head)`
- Formal database writes: `0`

Task 28A-R2C discovered PostgreSQL 16.14 binaries through the existing Windows service `PathName`, initialized a fresh project-local cluster under `.runtime/task28a/postgres/data`, and provisioned the test-only role and database. The existing `127.0.0.1:55432` instance and `energy_maintenance` database were not operated.

## Provisioning Guard

`backend/scripts/provision_task28a_test_database.py` was run first in dry-run mode and then with explicit `--apply` while `TASK28A_PG_ADMIN_URL` existed only in the current PowerShell process. It:

- rejects formal and PostgreSQL maintenance databases;
- requires a privileged temporary cluster administrator only for apply;
- creates the test role with `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`;
- verifies the test database owner;
- writes the test connection only to ignored `.env.task27a.test.local`;
- never prints the generated test-role password or administrator URL.

The initial apply exposed PostgreSQL DDL parameter binding incompatibility for `CREATE ROLE ... PASSWORD $1`. The provisioner now uses psycopg `sql.Literal` for the password literal while retaining identifier-safe composition. Dry-run and apply both completed after that correction.

## Evidence

| Check | Result |
| --- | --- |
| Project-local cluster initialization | passed |
| Cluster restart check | passed |
| Cluster administrator connection | passed |
| Provisioner dry-run | passed |
| Provisioner apply | passed |
| Test role/database owner verification | passed |
| `alembic upgrade head` on test database | passed |
| Final Alembic current | `20260712_0015 (head)` |
| Formal database write | not executed |

The isolated cluster was stopped after verification. Its project-local data and logs remain available for audit; it does not run as a Windows service.
