# Runtime Verification

## Environment Identification

| Check | Result | Evidence |
|---|---|---|
| Energy-Maintenance backend | running on `127.0.0.1:8012` | Uvicorn process command references `app.main:app` from this backend venv. |
| Port 8000 | no listener during audit | `Get-NetTCPConnection` |
| Port 8010 | no listener during audit | `Get-NetTCPConnection` |
| PostgreSQL | running on `127.0.0.1:55432` | standalone `postgres.exe` process |
| Port 5432 | no listener during audit | `Get-NetTCPConnection` |
| PostgreSQL Windows service | Stopped / Disabled | `Get-Service postgresql-x64-16` |
| Application environment | development | sanitized settings import |

No process was started, stopped or reconfigured by this audit.

## Backend And HTTP

| Check | Result | Key output |
|---|---|---|
| `GET /api/health` | passed | HTTP 200, project `Energy-Maintenance`, status `running`. |
| `GET /api/system/status` | passed | HTTP 200, `database_status=online`. |
| `GET /openapi.json` | passed | Title `Energy-Maintenance`, version `0.1.0`, 233 paths. |
| `GET /` | passed | HTTP 200, SPA entry returned. |
| `GET /dashboard` | passed | HTTP 200, SPA fallback returned. |
| `GET /docs` | passed | HTTP 200. |
| Final smoke | passed | 23 checks, 0 failures; retrieval write disabled. |

The final smoke covered health, static SPA, OpenAPI, admin login, current user, system statistics, devices, knowledge, contributions, record lists, SOP, tasks, record center, graph, review, corrections and model-gateway status. It did not perform a retrieval POST because that would create a `qa_records` row.

Security note: the smoke script used its built-in local-development admin fallback because `FULL_SMOKE_ADMIN_PASSWORD` was absent, and the running system accepted it. The credential value is intentionally not recorded. Evidence: `scripts/final_smoke_test.ps1:10-13` and the successful login check.

## Database And Migrations

| Command/check | Result | Notes |
|---|---|---|
| Read-only PostgreSQL version query | passed | PostgreSQL 16.14. |
| Public table count | passed | 58 including `alembic_version`. |
| `alembic heads` | passed | `20260712_0015 (head)`. |
| `alembic current` | passed | `20260712_0015 (head)`. |
| `alembic history` | passed | Linear 15-revision chain. |
| ORM/DB table comparison | passed | 57 ORM tables, no missing application table. |
| ORM/DB column comparison | passed | No column mismatch found. |
| `alembic upgrade head` | not executed | Prohibited by audit scope. |

The live database is structurally aligned with the working tree, but not reproducible from Git HEAD because revisions 0009-0015 are untracked.

## Backend Compilation And Tests

| Command/check | Result | Exit/status |
|---|---|---|
| `python -m compileall app` with temporary pycache prefix | passed | Exit 0. |
| `pytest --collect-only -q -p no:cacheprovider` | passed | 485 tests collected; one Starlette/httpx deprecation warning. |
| Seven isolated Task 25G unit tests | passed | 7 passed in 1.10s. |
| Full pytest | not executed | Unsafe against current configured database. |
| Lint | not executed | No configured repository lint command found. |
| mypy | not executed | No configured command found. |

Why full pytest was not safe:

- `backend/tests/conftest.py:1-13` only adjusts import paths and does not override `SessionLocal` or install rollback fixtures.
- `backend/tests/integration/test_ambiguous_query_clarification.py:3-26` opens `SessionLocal`, deletes rows and commits.
- Other integration tests perform inserts/commits against the configured database.

Running the full suite could change formal development data, which violates this audit's read-only rule.

## Frontend

| Command/check | Result | Notes |
|---|---|---|
| `npx vue-tsc --noEmit` | passed | Exit 0. |
| Vite production build to TEMP | passed | 1,976 modules, 62 files, 718,723 bytes, 2.25s. |
| Exact `npm run build` | not executed | Would update normal build/tsbuildinfo output; equivalent typecheck and Vite build were run read-only. |
| Frontend/API integration script | passed | 133 frontend calls, 133 matches, 0 missing, 0 fake. |
| Browser visual/button test | not executed | Not required for safe first-pass audit and would need controlled login/write data. |

## External And Advanced Capabilities

| Capability | Current audit result | Reason |
|---|---|---|
| Cloud text model | BLOCKED | Configured/enabled state observed, but no real call permitted. |
| MIMO/vision | BLOCKED | No real external request permitted. |
| OCR | BLOCKED | Current runtime flag disabled; no engine/API call. |
| Local llama.cpp | BLOCKED | Runtime flag disabled; no local model service check. |
| Embedding API | BLOCKED | Enabled/configured state observed; no real call permitted. |
| DashVector | BLOCKED | Enabled/configured state observed; no query/write permitted. |
| Knowledge graph current production grounding | PARTIAL | Current R2 evidence shows only one grounded edge/relation type. |
| LoongArch/Kylin physical deployment | BLOCKED | No target host. |

Historical reports may document prior controlled calls. This report only claims what was safely reverified against the current working tree and runtime.

## Runtime Conclusion

Backend read-side core runtime, PostgreSQL connectivity, OpenAPI, static frontend serving, TypeScript checking and production compilation are healthy. The global test result is `PARTIAL`, not `PASSED`, because only collection and a safe subset ran. Mutating business workflows and external providers are implemented but unverified or blocked in this audit.

