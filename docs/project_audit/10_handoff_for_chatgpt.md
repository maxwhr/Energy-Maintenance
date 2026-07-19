# Energy-Maintenance Audit Handoff

## 1. Audit Baseline

- Branch: `main`
- Commit: `53145339c66b6efed489156ea68cf55d24161ab8`
- Audit date: 2026-07-16
- Environment: Windows PowerShell, existing backend on 8012, standalone PostgreSQL 16.14 on 55432.
- Worktree dirty: yes; 855 status entries, 152 tracked changes, 703 untracked paths, staged 0.
- Unverified: write APIs, full pytest, external providers, browser button flows, physical LoongArch/Kylin deployment.
- No business code, migration, environment, dependency or data was modified by this audit.

## 2. Actual Product

The working tree implements a Huawei/Sungrow PV-inverter maintenance workbench. It manages device/knowledge/media data, traceable retrieval, diagnosis, SOP/tasks/workflows, review, record center, agents, provider adapters and a PostgreSQL knowledge graph. It is not merely a chat UI, but some advanced AI paths remain configuration-dependent or quality-gated.

## 3. Actual Stack

- Frontend: Vue 3, Vite 8, TypeScript 6, Router, Pinia, Axios, Tailwind, Lucide. Evidence: `frontend/package.json`.
- Backend: FastAPI, Uvicorn, Pydantic, SQLAlchemy 2, Alembic, psycopg 3, HTTPX, Pillow, pypdf, python-docx. Evidence: `backend/pyproject.toml`.
- Database: PostgreSQL; 57 ORM application tables and 15 Alembic revisions.
- Storage: PostgreSQL metadata plus local backend filesystem for uploads/media.
- AI: keyword retrieval, optional Embedding/DashVector, model gateway, provider adapters, OCR/multimodal adapters and PostgreSQL KG.
- Deployment: `deploy/loongarch/` native venv/PostgreSQL/systemd/Nginx path; no formal Docker dependency.

## 4. Actual Architecture

- Entry/router: `backend/app/main.py` mounts 25 route groups under `/api`; OpenAPI has 233 paths.
- Backend layering: route -> service -> repository -> SQLAlchemy model.
- Frontend: 33 routed pages, centralized `/api` Axios client and JWT/role guards.
- Auth: PBKDF2 password hashes and HS256 bearer JWT; logout is stateless.
- Knowledge: upload -> parser -> chunker -> PostgreSQL -> review gate.
- Retrieval: query understanding -> PostgreSQL keyword -> optional Embedding/DashVector -> fusion/rerank -> citation validation -> QA persistence.
- Workflows: diagnosis/SOP/tasks/review/agent/graph use dedicated policies and PostgreSQL audit records.

## 5. Feature Completion

### Verified In This Audit

- backend health, system/database status and OpenAPI;
- SPA root/dashboard/docs fallback;
- admin login and current-user read through smoke;
- read-side system stats, devices, knowledge, contributions, records, SOP, tasks, graph, review, corrections and model-gateway status;
- PostgreSQL/Alembic/ORM schema consistency;
- frontend/API method/path matching (133/133);
- backend compile;
- TypeScript check and temporary production build.

### Implemented But Not Verified Here

- user/device CRUD writes;
- document upload/parse/chunk/reparse/archive;
- retrieval query and QA record write;
- diagnosis write;
- SOP/task/workflow mutations;
- approvals/contribution conversion;
- media uploads, OCR job persistence, agent runs and graph writes;
- backup/restore and target deployment scripts.

### Partial

- dynamic role/permission/menu management: roles are fixed strings and menus are static;
- knowledge graph: tables/API exist, current Chinese production grounding is insufficient;
- AI provider gateway/model status: code exists, current real-call availability not verified;
- full regression testing: collection passes but suite is not database-isolated.

### Confirmed Broken

- Reproducible delivery from Git HEAD: current source/migrations are not fully tracked.
- Viewer navigation consistency: some viewer-permitted routes are hidden by parent menu roles.

### Documentation Only/Not Found

- no dedicated notifications subsystem;
- no independent inspection-task/result subsystem;
- no report/export or bulk-import subsystem;
- no dynamic menu/role/permission administration;
- no Redis/message queue/object storage/Neo4j.

## 6. Current Runtime

- Backend start: already running and verified on 8012.
- Database: online on 55432; Windows service is stopped/disabled and standalone process supplies it.
- Frontend build: passed using `vue-tsc --noEmit` plus Vite build to TEMP.
- Tests: 485 collected; seven safe isolated tests passed; full suite not run because it can write the active configured database.
- Main environment issue: local DB does not survive reboot as a managed service.
- Main code/repository issue: current working tree is not reproducible from HEAD.

## 7. Most Important Issues

1. `AUD-001 P1`: 703 untracked paths and seven untracked migrations make current runtime unreproducible.
2. `AUD-002 P1`: built-in local smoke admin fallback credential authenticates.
3. `AUD-003 P1`: full pytest can mutate the configured database; no global test DB isolation.
4. `AUD-004 P1`: current Chinese KG grounding has only one usable edge/relation type.
5. `AUD-005 P1`: PostgreSQL Windows service is stopped/disabled; standalone process is not reboot durable.
6. `AUD-006 P1`: LoongArch/Kylin physical acceptance is absent.
7. `AUD-007 P2`: upload can leave an orphan file before document persistence.
8. `AUD-008 P2`: up to 50 MB uploads are buffered in memory.
9. `AUD-009 P2`: logout does not revoke JWT; no refresh flow.
10. `AUD-010 P2`: success code is either 0 or 200.
11. `AUD-011 P2`: root README scope conflicts with v1 rules.
12. `AUD-012 P2`: menu parent roles hide viewer-permitted routes.
13. `AUD-013 P2`: no CI/frontend test/lint gate found.
14. `AUD-014 P2`: external provider availability was not current-audit verified.
15. `AUD-015 P3`: legacy frontend/generated assets/package naming create ambiguity.

Full detail: `docs/project_audit/06_bug_and_risk_register.md`.

## 8. Main Architecture Problems

1. Git/worktree is the only source of the current system; HEAD is obsolete.
2. Tests and application share the same `SessionLocal` configuration.
3. External-provider state is environment-dependent and historical reports can become stale.
4. Response helpers are duplicated and use two success codes.
5. Route and menu role metadata are duplicated.
6. Filesystem and database cannot participate in one atomic transaction.
7. No CI clean-clone gate.
8. Extensive historical reports obscure current operational truth.
9. Local database startup is not service-managed.
10. Target native dependency compatibility remains physical-host dependent.

## 9. Main Data Consistency Problems

1. Current DB schema matches the working tree but not the committed revision set.
2. Upload can create an unreferenced file if validation/initial insert fails.
3. Full pytest may add/delete rows in the active configured database.
4. Soft-delete/archive semantics are module-specific rather than globally uniform.
5. External vector state requires PostgreSQL reconciliation; no current remote reconciliation was run.
6. KG production graph has insufficient grounded edge coverage.

## 10. RAG Actual State

The RAG implementation is real code with PostgreSQL keyword retrieval, Chinese expansion, optional Embedding/DashVector, hybrid fusion/rerank, citation validation, answer boundaries and QA persistence. Default configuration code favors keyword mode and falls back when vector service is unavailable. Current real provider availability was not tested. Intended vector dimension/index naming indicates 1024, but the provider response dimension was not re-probed. Current KG context is not applied because the reviewed Chinese graph is too sparse.

See `docs/project_audit/07_rag_ai_audit.md`.

## 11. Deployment Actual State

There is an executable-looking native deployment tree with systemd, Nginx, venv, PostgreSQL, backup, migration, health and rollback scripts. Static portability/rollback tests passed. Real LoongArch/Kylin execution, target wheel builds, service activation, backup restore and end-to-end acceptance did not run. Do not claim physical deployment success.

## 12. Test Actual State

- Test files: 403.
- Tests collected: 485.
- Collection: passed.
- Safe isolated tests: 7 passed.
- Full pytest: not run for data-safety reasons.
- Frontend automated tests: no configured test script found.
- Frontend type/build: passed.
- Read-only smoke: 23/23 passed.
- Key gaps: isolated DB, mutating business flows, current external providers, browser role/button matrix, real LoongArch.

## 13. Priority Next Audits

1. Git/release baseline: classify and commit current source/migrations without generated/runtime data.
2. Test data isolation: dedicated database/schema guard, then full pytest.
3. Authentication hardening: remove fallback credential and test token revocation policy.
4. Controlled write-flow audit: upload -> chunks -> retrieval -> QA plus diagnosis/SOP/task/review, with row-count rollback guards.
5. KG expert-review/grounding quality audit.
6. Controlled external-provider acceptance with config hash and no-secret evidence.
7. Real LoongArch/Kylin deployment acceptance.

## 14. Open Questions

- Which untracked paths are intended release source versus disposable experiment/runtime output?
- Is the current standalone PostgreSQL database development-only or the intended final acceptance database?
- Should viewer accounts see Agent Workbench and Review Center directly?
- Which historical external-provider acceptance remains valid for the current credentials/configuration?
- What expert-reviewed KG relation coverage is required before production enablement?
- Is a token revocation/refresh policy required for the delivery security profile?

## 15. Key File Index

- `AGENTS.md`: product and engineering constraints.
- `backend/app/main.py`: backend entry and router registration.
- `backend/app/core/config.py`: environment/provider/runtime settings.
- `backend/app/core/database.py`: SQLAlchemy engine/session.
- `backend/alembic/versions/`: 15-revision schema chain in working tree.
- `backend/app/services/knowledge_service.py`: upload/parse/chunk transaction.
- `backend/app/services/retrieval_service.py`: retrieval, references and QA persistence.
- `backend/app/services/maintenance_task_service.py`: task CRUD/workflow orchestration.
- `backend/app/services/knowledge_graph_service.py`: graph CRUD/RBAC/business context.
- `frontend/src/router/index.ts`: page routes/guard.
- `frontend/src/router/menus.ts`: menu/role visibility.
- `frontend/src/utils/request.ts`: API envelope/auth handling.
- `deploy/loongarch/`: native target deployment assets.
- `docs/25G_R2_current_chinese_knowledge_graph_grounding_report.md`: current KG grounding limit.
- `docs/project_audit/06_bug_and_risk_register.md`: evidence-backed issue register.
- `docs/project_audit/audit_manifest.json`: machine-readable audit summary.

