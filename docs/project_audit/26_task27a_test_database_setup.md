# Task 27A-R3 Isolated PostgreSQL Test Database Setup

## Current Status

`BLOCKED_ADMIN_ACTION_REQUIRED`

The application role cannot create databases, no existing database name containing `_test` or `task27a` was found, and `TASK27A_ADMIN_DATABASE_URL` was not configured. Production database fallback is prohibited.

## Target

- Host: `127.0.0.1`
- Port: `55432`
- Target database: `energy_maintenance_task27a_test`
- Owner: `energy_user`
- Encoding: `UTF8`
- Template: `template0`

No administrator password or connection URL belongs in this document, source control, `.env.example`, command output, or reports.

## Administrator Action

Connect to the native PostgreSQL instance as a database administrator and run:

```sql
CREATE DATABASE energy_maintenance_task27a_test
    OWNER energy_user
    ENCODING 'UTF8'
    TEMPLATE template0;
```

Verification:

```sql
SELECT datname, pg_get_userbyid(datdba) AS owner, pg_encoding_to_char(encoding) AS encoding
FROM pg_database
WHERE datname = 'energy_maintenance_task27a_test';

SELECT has_database_privilege(
    'energy_user',
    'energy_maintenance_task27a_test',
    'CONNECT,CREATE,TEMPORARY'
);
```

The provisioning helper defaults to dry-run:

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
uv run python scripts\provision_task27a_test_database.py
```

Optional administrator-assisted execution requires the administrator URL only in the current process environment:

```powershell
$env:TASK27A_ADMIN_DATABASE_URL="<administrator PostgreSQL URL>"
uv run python scripts\provision_task27a_test_database.py --apply
Remove-Item Env:TASK27A_ADMIN_DATABASE_URL
```

The helper refuses the production database, PostgreSQL maintenance/template databases, unsafe identifiers, and any name without `_test` or `task27a`. It never drops an existing database.

## Alembic And Acceptance Commands

Only after verifying the target database name:

```powershell
$env:DATABASE_URL="postgresql+psycopg://energy_user:<local-test-password>@127.0.0.1:55432/energy_maintenance_task27a_test"
$env:APP_ENV="test"
$env:ALLOW_REAL_EXTERNAL_API="false"

uv run python -c "from app.core.database import engine; assert '_test' in str(engine.url.database).lower() or 'task27a' in str(engine.url.database).lower(); print(engine.url.database)"
uv run python -m alembic -c alembic.ini upgrade head
uv run python scripts\check_task27a_qa_persistence_flow.py
```

Do not run these commands with `energy_maintenance`.

## Rollback

Rollback is a separate, explicitly authorized administrator action after confirming that no test process is connected and no reusable acceptance evidence is needed:

```sql
DROP DATABASE energy_maintenance_task27a_test;
```

Never automate this rollback from the application role, and never apply it to `energy_maintenance`.
