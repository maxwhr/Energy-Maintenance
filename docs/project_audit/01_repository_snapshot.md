# Repository Snapshot

## Git State

| Item | Observed value |
|---|---|
| Branch | `main` |
| HEAD | `53145339c66b6efed489156ea68cf55d24161ab8` |
| HEAD date | 2026-07-06 01:23:54 +08:00 |
| Commit count visible | 4 |
| Worktree entries | 855 |
| Tracked changed paths | 152 |
| Untracked paths | 703 |
| Tracked deletions | 53 |
| Staged paths | 0 |
| Tracked diff | 5,970 insertions, 760 deletions across 152 files |

The live application is materially ahead of Git HEAD. In particular, migrations `20260601_0009` through `20260712_0015`, current ORM models, routes and many RAG/workflow services are untracked. A fresh clone at HEAD cannot reproduce the running schema or application.

Evidence:

- `git status --short -- backend/alembic/versions backend/app frontend/src deploy/loongarch`
- `backend/alembic/versions/20260601_0009_add_high_precision_rag_evaluation.py`
- `backend/alembic/versions/20260712_0015_add_maintenance_workflow_links.py`
- `backend/app/models/maintenance_workflow.py`
- `backend/app/api/routes/maintenance_workflows.py`

## Repository Composition

Counts exclude generated dependency/build/upload trees from detailed analysis.

| Area | Observed scale |
|---|---:|
| Python files | 1,166 |
| Markdown files | 164 |
| Vue files | 66 |
| TypeScript files | 42 |
| PowerShell scripts | 14 |
| Shell scripts | 29 |
| Backend API files | 25 |
| Backend model files | 20 |
| Backend repository files | 30 |
| Backend schema files | 35 |
| Backend service files | 205 |
| Frontend routed pages | 33 |
| Backend tests | 403 files |
| Collected pytest tests | 485 |
| Alembic revisions | 15 |

## Main Entrypoints

- Backend application: `backend/app/main.py`
- Database configuration: `backend/app/core/database.py`
- Backend configuration: `backend/app/core/config.py`
- Alembic environment: `backend/alembic/env.py`
- Frontend application: `frontend/src/main.ts`
- Frontend router: `frontend/src/router/index.ts`
- Frontend menus: `frontend/src/router/menus.ts`
- Frontend HTTP client: `frontend/src/utils/request.ts`
- Frontend build: `frontend/package.json`, `frontend/vite.config.ts`
- Native deployment: `deploy/loongarch/`

## Actual Technology Stack

### Backend

FastAPI, Uvicorn, Pydantic/pydantic-settings, SQLAlchemy 2.x, Alembic, PostgreSQL through psycopg 3, HTTPX, Pillow, pypdf and python-docx. Evidence: `backend/pyproject.toml:7-31`.

### Frontend

Vue 3, Vite 8, TypeScript 6, Vue Router, Pinia, Axios, Tailwind CSS and Lucide icons. The current `package.json` package name is `cupproject`, which is a naming remnant. Evidence: `frontend/package.json`.

### Data And Infrastructure

- Formal relational source of truth: PostgreSQL.
- Upload/media storage: local filesystem under backend storage paths.
- Vector search: optional DashVector adapter; fake in-memory adapter is explicitly test-only.
- Redis: not found.
- Message queue/background worker: not found.
- Object storage: not found.
- External graph database: not found; graph data is PostgreSQL-backed.
- Formal deployment: native LoongArch/Kylin, Python venv, PostgreSQL, systemd and Nginx.
- Docker files: none found.

## Frontend And Static Assets

The current source frontend is `frontend/`. The repository also contains a legacy backup directory and a large set of changed/deleted/rebuilt static hashed assets. This creates delivery ambiguity until the intended source and generated artifact policy is committed and documented.

Relevant paths:

- `frontend/`
- `frontend_legacy_before_cupProject_20260611_185550/`
- `backend/static/frontend/`
- root `node_modules/`

## Tests And Quality Tooling

- pytest and pytest-asyncio are configured as development dependencies.
- 485 tests collect successfully.
- No repository-wide isolated database fixture is present in `backend/tests/conftest.py:1-13`.
- No frontend test script, lint script or CI workflow was found.
- Frontend scripts provide only `dev`, `build` and `preview`.
- Safe compilation, static API integration, TypeScript checking and production build passed in this audit.

## Reproducibility Conclusion

The current machine can run the working tree, but the repository at HEAD is not a reproducible delivery unit. This is the dominant repository-level risk and must be resolved before release tagging, handoff or target-machine deployment.

