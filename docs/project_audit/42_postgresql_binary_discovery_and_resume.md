# Task 28A-R2C PostgreSQL Binary Discovery and Resume

## Result

`PASSED_TEST_DATABASE_ACCEPTANCE`

Task 28A-R2C resumed at the binary-discovery stage without repeating source migration, credential discovery, homepage work, or formal-database operations.

## Authorized Discovery Evidence

Read-only Windows service metadata reported `postgresql-x64-16` as stopped and disabled, with executable `PathName` rooted at `D:\Work Space\PostgreSQL\bin`. No active `postgres` process was found before the Task 28A project-local start.

| Binary | Version |
| --- | --- |
| `initdb.exe` | PostgreSQL 16.14 |
| `pg_ctl.exe` | PostgreSQL 16.14 |
| `psql.exe` | PostgreSQL 16.14 |
| `createdb.exe` | PostgreSQL 16.14 |
| `postgres.exe` | PostgreSQL 16.14 |
| `pg_isready.exe` | PostgreSQL 16.14 |

The standard Program Files PostgreSQL roots had no usable version directories. The service-derived binary directory was the only candidate used. System PATH and Windows service configuration were not changed.

## Isolated Execution

1. Created the cluster only under `.runtime/task28a/postgres`.
2. Generated the cluster administrator password with the Windows cryptographic random-number API; the temporary password file was deleted.
3. Initialized UTF8 and SCRAM-SHA-256 authentication.
4. Repeated start, stop, start, and `pg_isready` checks on `127.0.0.1:55433`.
5. Ran the guarded provisioner dry-run and apply using a current-process-only administrator URL.
6. Migrated only `energy_maintenance_task27a_test` to `20260712_0015 (head)`.
7. Imported and validated the corpus, QA persistence, Record Center, and two manual-confirmation multimodal cases.
8. Stopped the cluster and confirmed port `55433` was released.

## Corrections Found During Real Acceptance

- PostgreSQL does not permit a bound parameter in the `PASSWORD` clause of `CREATE ROLE`; the guarded provisioner now uses a safely quoted psycopg SQL literal.
- The cross-modal plan default scope was inconsistent with the active Huawei SUN2000 query-aware scope; it now defaults to the same formal scope identifier.

Both corrections were verified with backend compilation and three targeted unit/integration tests.

## Boundaries Preserved

- No connection, inspection, migration, or write targeted `127.0.0.1:55432`.
- No formal `energy_maintenance` database write occurred.
- No Docker, SQLite, embedding, vector rebuild, external provider, OCR, MIMO, cloud, or local-model call occurred.
- No secret, administrator URL, or generated password was printed or serialized into an audit report.

## Follow-up

The controlled formal import gate remains closed. A later task must obtain explicit authorization and expert review before importing any Huawei document into the formal database.
