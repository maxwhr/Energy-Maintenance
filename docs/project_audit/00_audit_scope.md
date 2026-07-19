# Energy-Maintenance Audit Scope

## Baseline

- Audit time: 2026-07-16 10:57 +08:00
- Workspace: `D:\Work Space\Energy-Maintenance`
- Branch: `main`
- Commit: `53145339c66b6efed489156ea68cf55d24161ab8` (`5314533`, `前端替换剩3页`)
- Worktree: dirty; 855 status entries (152 tracked changes and 703 untracked paths), with no staged changes.
- Audit mode: read-only product, code, database, runtime, test and deployment audit.

## Scope

The audit covered:

1. Git history and worktree reproducibility.
2. FastAPI application entry, middleware, authentication, RBAC, routes, services, repositories, models and schemas.
3. Vue 3 routes, menus, stores, API wrappers, request interception and production build.
4. Alembic chain, SQLAlchemy metadata and the currently connected PostgreSQL schema.
5. Knowledge upload, parsing, retrieval, diagnosis, SOP, task, record-center, review, media, multimodal, agent, graph and external-provider paths.
6. Safe runtime checks against the already-running Energy-Maintenance process.
7. Test discovery and selected tests that do not write formal data.
8. LoongArch/Kylin native deployment assets and declared capability boundaries.

## Excluded Or Not Fully Audited

- No write API was invoked, so current-code document upload, retrieval record creation, diagnosis creation, task mutation and review mutation remain unverified in this audit.
- No full pytest run was performed because the suite imports `SessionLocal` from the live configuration and contains direct `commit`, `insert` and `delete` operations without a global isolated-test-database fixture.
- No real Cloud LLM, MIMO/Vision, OCR, Embedding or DashVector request was made.
- No real LoongArch/Kylin host was available; target-machine installation, wheel building, systemd and Nginx activation remain blocked.
- Browser visual and button-by-button testing was not repeated. Static SPA routes, built assets and HTTP fallback were checked.
- Uploaded file contents, model files, secrets and private runtime evidence were not opened or copied into reports.

## Safety Constraints Applied

- No business, frontend, backend, migration, dependency or environment file was changed.
- No `alembic upgrade`, data seed, cleanup, upload, retrieval write or destructive command was run.
- Build and bytecode output were redirected to the system temporary directory where possible.
- No real third-party quota was consumed.
- Secret values, tokens and credentials are deliberately omitted.
- Only `docs/project_audit/` is written by this audit.

## Commands Executed

| Command or check | Result | Notes |
|---|---|---|
| `git status --short`, branch/log/diff statistics | passed | 855 worktree entries; no staged changes. |
| Repository inventory using `rg --files` and grouped counts | passed | Generated, virtualenv and upload trees were excluded from detailed enumeration. |
| Port/process/service checks for 8000/8010/8012/5432/55432 | passed | Energy-Maintenance is on 8012; PostgreSQL is on 55432. |
| Sanitized settings import | passed | PostgreSQL driver/host/port/database and feature flags only; no secret values printed. |
| `GET /api/health`, `/api/system/status`, `/openapi.json`, `/`, `/dashboard`, `/docs` | passed | Existing process identified as Energy-Maintenance. |
| PostgreSQL read-only version/table query | passed | PostgreSQL 16.14; 58 public tables including `alembic_version`. |
| `alembic heads/current/history` | passed | Single current head: `20260712_0015`. No migration executed. |
| SQLAlchemy metadata vs PostgreSQL schema comparison | passed | 57 ORM tables; only DB-only table is `alembic_version`; no column mismatch found. |
| Frontend/API static integration checker | passed | 133 calls matched, 0 missing, 0 fake. |
| `final_smoke_test.ps1` against 8012 with retrieval write disabled | passed | 23 passed, 0 failed. |
| `compileall` with temporary pycache prefix | passed | Exit code 0. |
| `pytest --collect-only` without cache | passed | 485 tests collected; one deprecation warning. |
| Seven isolated Task 25G unit tests | passed | 7 passed in 1.10 seconds. |
| `vue-tsc --noEmit` | passed | Exit code 0. |
| Vite production build to temporary output directory | passed | 1,976 modules; 62 files; 718,723 bytes. |

## Known Environmental Limits

- Windows service `postgresql-x64-16` is `Stopped` and `Disabled`; the active database is a standalone `postgres.exe` process on 55432.
- PowerShell attempted to load a disabled profile on each shell invocation. This produced a non-fatal profile warning and did not invalidate command results.
- Ports 8000, 8010 and 5432 were not used by this audit; no other-project process was stopped.
- Current external-provider flags indicate some real-call paths are enabled, but this audit deliberately did not invoke them; current availability is therefore `BLOCKED`, not `VERIFIED`.

