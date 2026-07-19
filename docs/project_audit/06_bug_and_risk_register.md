# Bug And Risk Register

## Severity Summary

| Severity | Count |
|---|---:|
| P0 | 0 |
| P1 | 6 |
| P2 | 8 |
| P3 | 1 |

No P0 issue was demonstrated by the safe checks. The running read-side core and current schema are healthy; the highest risks concern delivery reproducibility, security defaults, test isolation and target-environment acceptance.

## AUD-001 - Working Tree Cannot Reproduce The Running System

- Type: `DEPLOYMENT_RISK`
- Severity: `P1`
- Module: repository/release management
- Location: Git worktree; `backend/alembic/versions/20260601_0009...` through `20260712_0015...`; numerous untracked backend/frontend/deploy files.
- Discovery: Git status/diff audit.
- Evidence: 855 status entries, 703 untracked paths, 152 tracked changes; current DB head is 0015 while migrations 0009-0015 are untracked.
- Reproduction: checkout HEAD `5314533` in a fresh clone and compare available revisions/routes with current OpenAPI/database.
- Expected: release source, migration chain and generated assets are intentionally versioned and reproducible.
- Actual: the machine runs a working tree substantially ahead of HEAD.
- Impact: fresh deployment, rollback, peer review and incident recovery cannot reliably reconstruct the current application.
- Root cause: long-running task work accumulated without controlled commits and generated-artifact policy.
- Recommendation: inventory and review all changes; split source/migrations/docs from generated/runtime files; commit a coherent release baseline; verify a clean-clone build/migrate/smoke.
- Suggested test: clean-clone reproducibility pipeline with PostgreSQL migration to 0015, frontend build and read-only smoke.
- Fix cost/risk: high / high.
- Confidence: high.

## AUD-002 - Known Local Development Admin Fallback Is Accepted

- Type: `SECURITY_RISK`
- Severity: `P1`
- Module: authentication/smoke configuration
- Location: `scripts/final_smoke_test.ps1:10-13`; running development configuration.
- Discovery: current smoke execution without `FULL_SMOKE_ADMIN_PASSWORD`.
- Evidence: script reported use of its built-in local fallback and admin login succeeded. The value is intentionally omitted.
- Reproduction: run the smoke script without the password environment variable against the current development instance.
- Expected: no predictable credential should authenticate outside an explicitly seeded disposable environment.
- Actual: the fallback credential authenticates on the running instance.
- Impact: anyone with source/script knowledge and local network access may obtain admin privileges.
- Root cause: seeded/default development account remains active and compatible with the smoke fallback.
- Recommendation: require an explicit smoke credential; rotate/disable the fallback account before shared deployment; make startup or smoke fail closed when no explicit credential is supplied.
- Suggested test: assert fallback password rejection after rotation and explicit secret-based smoke success.
- Fix cost/risk: low / medium.
- Confidence: high.

## AUD-003 - Full Pytest Suite Is Not Isolated From The Configured Database

- Type: `DATA_INTEGRITY_RISK`
- Severity: `P1`
- Module: test infrastructure
- Location: `backend/tests/conftest.py:1-13`; examples `tests/integration/test_ambiguous_query_clarification.py:3-26` and other integration tests importing `SessionLocal`.
- Discovery: test collection and fixture/source audit.
- Evidence: global conftest only adds import paths; integration tests open current `SessionLocal`, insert/delete and commit.
- Reproduction: point `.env` at a populated database and run full pytest.
- Expected: tests use a dedicated test database/schema or rollback fixture and refuse non-test databases.
- Actual: suite behavior depends on the active application `DATABASE_URL` and can mutate it.
- Impact: development/formal data contamination or deletion; prevents safe global regression execution.
- Root cause: integration tests were added incrementally without a mandatory database isolation contract.
- Recommendation: introduce an explicit test DATABASE_URL guard, per-session test schema/database, transactional rollback fixtures and a hard refusal for non-test database names.
- Suggested test: run the full suite twice and prove the formal database row/hash inventory is unchanged.
- Fix cost/risk: medium / medium.
- Confidence: high.

## AUD-004 - Current Chinese Knowledge Graph Grounding Is Below Production Threshold

- Type: `MISSING_FEATURE`
- Severity: `P1`
- Module: knowledge graph/RAG grounding
- Location: `docs/25G_R2_current_chinese_knowledge_graph_grounding_report.md`; `backend/app/services/knowledge_graph_production_scope_service.py` and grounding services.
- Discovery: current Task 25G R2 evidence audit.
- Evidence: 68 active facts, 10 exact support candidates, but only one grounded edge and one relation type; production KG context remains empty and 58 candidates require manual review.
- Reproduction: use the frozen R2 current-Chinese grounding checks/report.
- Expected: reviewed, diverse, source-traceable graph edges enrich retrieval/diagnosis without unsupported facts.
- Actual: graph infrastructure exists, but production-scope grounding is too sparse to apply.
- Impact: graph-enhanced retrieval/diagnosis/SOP should not be marketed as production-effective.
- Root cause: insufficient reviewed Chinese source evidence and relation diversity, not missing graph tables.
- Recommendation: expert-review the 58 candidates, expand validated relation coverage, rerun grounding/ablation gates and keep graph fallback disabled until thresholds pass.
- Suggested test: frozen Chinese benchmark with edge evidence integrity, relation diversity, answer-grounding and no-regression metrics.
- Fix cost/risk: high / medium.
- Confidence: high.

## AUD-005 - PostgreSQL Does Not Survive Reboot Automatically

- Type: `DEPLOYMENT_RISK`
- Severity: `P1`
- Module: local runtime/database operations
- Location: Windows service `postgresql-x64-16`; standalone PostgreSQL process on 55432.
- Discovery: service, process and port inspection.
- Evidence: service is `Stopped` and `Disabled`; database availability depends on manually started standalone `postgres.exe`.
- Reproduction: reboot or stop the standalone process, then call `/api/system/status`.
- Expected: managed PostgreSQL service starts reliably before the application.
- Actual: current local database is process-based and not service-managed.
- Impact: unexpected outage after reboot and inconsistent startup scripts/operator experience.
- Root cause: native Windows service startup remains unrepaired; standalone fallback became the active environment.
- Recommendation: repair native service startup under administrator control or formalize a clearly managed non-production startup script; verify restart and dependency order.
- Suggested test: reboot acceptance, service auto-start, `pg_isready`, Alembic current and application health.
- Fix cost/risk: medium / medium.
- Confidence: high.

## AUD-006 - Formal LoongArch/Kylin Target Has No Physical Acceptance

- Type: `DEPLOYMENT_RISK`
- Severity: `P1`
- Module: production deployment
- Location: `deploy/loongarch/REAL_MACHINE_ACCEPTANCE_CHECKLIST.md:1-16`; dependency risk manifests.
- Discovery: deployment artifact and report audit.
- Evidence: checklist remains unexecuted; manifests identify target builds for pydantic-core, Pillow, lxml and MarkupSafe.
- Reproduction: none on this Windows host; requires real `loongarch64` Kylin hardware.
- Expected: native wheel build, install, migration, systemd, Nginx, upload/parser and smoke evidence on the target.
- Actual: only source-level/static preparation is available.
- Impact: formal deployment compatibility and operational readiness cannot be claimed.
- Root cause: no target hardware/runtime acceptance window.
- Recommendation: execute the controlled real-machine checklist, build a signed wheelhouse, validate backup/rollback and capture sanitized evidence.
- Suggested test: `uname -m`, dependency imports, PostgreSQL migration, systemd/Nginx health and first-version closed loop.
- Fix cost/risk: high / high.
- Confidence: high.

## AUD-007 - Upload Can Leave Orphan Files Before Document Persistence

- Type: `DATA_INTEGRITY_RISK`
- Severity: `P2`
- Module: knowledge upload
- Location: `backend/app/services/knowledge_service.py:79-84,110-116,301-331`.
- Discovery: transaction/file ordering audit.
- Evidence: file is written before title validation and initial document commit; failure paths do not remove that file.
- Reproduction: upload a valid non-empty file with a whitespace-only explicit title, or force the first DB insert to fail.
- Expected: failed pre-persistence requests leave no unreferenced file, or record a recoverable quarantine item.
- Actual: saved file can remain without a document row.
- Impact: storage leakage and unclear retention/security handling.
- Root cause: filesystem write is outside a compensating transaction.
- Recommendation: validate all metadata first and add compensating deletion/quarantine on pre-document failure.
- Suggested test: failure injection before/at initial commit and orphan-directory assertion.
- Fix cost/risk: low / low.
- Confidence: high.

## AUD-008 - Large Uploads Are Buffered Fully In Memory

- Type: `PERFORMANCE_RISK`
- Severity: `P2`
- Module: knowledge/media upload
- Location: `backend/app/services/knowledge_service.py:310-315`; analogous media upload path.
- Discovery: source audit.
- Evidence: `await file.read()` occurs before limit rejection; configured maximum is 50 MB.
- Reproduction: issue multiple concurrent near-limit uploads.
- Expected: stream to a bounded temporary file while counting bytes.
- Actual: each request can retain the whole payload in process memory.
- Impact: memory spikes, worker exhaustion and denial-of-service amplification.
- Root cause: simple whole-buffer implementation.
- Recommendation: chunked streaming with early limit enforcement, temporary file cleanup and concurrency/load tests.
- Suggested test: concurrent 49/51 MB uploads with RSS and rejection timing assertions.
- Fix cost/risk: medium / medium.
- Confidence: high.

## AUD-009 - Logout Does Not Revoke Issued JWTs And No Refresh Flow Exists

- Type: `SECURITY_RISK`
- Severity: `P2`
- Module: authentication/session management
- Location: `backend/app/api/routes/auth.py:45-52`; `backend/app/core/config.py:16-18`.
- Discovery: route/config audit.
- Evidence: logout returns success without token state; no refresh route/service was found; default access lifetime is 1,440 minutes.
- Reproduction: authenticate, call logout, then reuse the same bearer token against `/api/auth/me`.
- Expected: security-sensitive deployment defines revocation/short-lived access and refresh policy.
- Actual: local token removal is the only immediate logout effect.
- Impact: stolen or copied tokens remain usable until expiry.
- Root cause: stateless first-version JWT design.
- Recommendation: shorten production expiry and add token version/revocation or access/refresh rotation with audit logging.
- Suggested test: token reuse after logout must fail; refresh replay must fail.
- Fix cost/risk: medium / high.
- Confidence: high.

## AUD-010 - API Success Codes Use Two Conventions

- Type: `MAINTAINABILITY_ISSUE`
- Severity: `P2`
- Module: API contract
- Location: `schemas/common.py:6-23`, `routes/auth.py:15-28`, `routes/devices.py:25-38`, `frontend/src/utils/request.ts:38-49`.
- Discovery: cross-layer response audit and smoke outputs.
- Evidence: success may be code 0 or 200; frontend has explicit dual handling.
- Reproduction: compare login/devices responses with health/knowledge responses.
- Expected: one documented success code.
- Actual: shape is unified but semantic value is not.
- Impact: duplicated helpers, client branching and ambiguous external integration contract.
- Root cause: coexistence of old cupProject convention and shared backend helper.
- Recommendation: choose one convention, migrate routes with contract tests and version/release notes.
- Suggested test: OpenAPI/runtime response-envelope contract across all routes.
- Fix cost/risk: medium / medium.
- Confidence: high.

## AUD-011 - Root README Product Scope Conflicts With Project Rules

- Type: `DOCUMENTATION_MISMATCH`
- Severity: `P2`
- Module: product documentation
- Location: `README.md:3`; `AGENTS.md:9-34`.
- Discovery: documentation/code scope comparison.
- Evidence: README describes generic photovoltaic/storage/power scenarios; project rules restrict v1 to Huawei/Sungrow PV inverters.
- Reproduction: read both introductions.
- Expected: public entry document states the current first-version scope.
- Actual: generic scope can mislead operators/reviewers.
- Impact: acceptance drift and over-broad delivery claims.
- Root cause: early README text was not updated consistently with later scope convergence.
- Recommendation: rewrite the README introduction and separate future expansion from v1.
- Suggested test: automated prohibited-scope phrase scan in release docs/UI.
- Fix cost/risk: low / low.
- Confidence: high.

## AUD-012 - Menu Parent Roles Hide Viewer-Permitted Routes

- Type: `CONFIRMED_BUG`
- Severity: `P2`
- Module: frontend navigation/RBAC UX
- Location: `frontend/src/router/menus.ts:74-83,114-122`; `frontend/src/router/index.ts:101-104,143-146`.
- Discovery: route/menu role comparison.
- Evidence: Agent Workbench and Review routes allow `viewer`, and child menu entries allow viewer, but parent groups exclude viewer.
- Reproduction: sign in as viewer and compare direct navigation with rendered menu.
- Expected: visible menu permissions match route permissions, or routes explicitly deny the role.
- Actual: direct route can be available while navigation entry is hidden.
- Impact: inconsistent user experience and incomplete discoverability of read-only capabilities.
- Root cause: parent role arrays were not normalized from child/route metadata.
- Recommendation: centralize role metadata or derive parent visibility from visible children.
- Suggested test: role-by-route-by-menu matrix for all four roles.
- Fix cost/risk: low / low.
- Confidence: high.

## AUD-013 - No CI, Frontend Test Command Or Configured Lint Gate Found

- Type: `MISSING_TEST`
- Severity: `P2`
- Module: quality engineering
- Location: repository root, `frontend/package.json`, `backend/pyproject.toml`.
- Discovery: configuration inventory.
- Evidence: no GitHub/GitLab/Azure/Jenkins workflow found; frontend scripts only dev/build/preview; no configured ruff/mypy/frontend test command.
- Reproduction: inspect package scripts and CI paths.
- Expected: clean-clone compile, migration/static schema, backend tests, frontend typecheck/build and secret checks run automatically.
- Actual: quality evidence is script/manual-task driven.
- Impact: regressions and missing files can be merged or handed off unnoticed.
- Root cause: iterative local development without a consolidated CI baseline.
- Recommendation: add CI after test DB isolation, with no real external calls and clean-clone reproducibility checks.
- Suggested test: protected-branch CI on Windows plus Linux/LoongArch static matrix.
- Fix cost/risk: medium / low.
- Confidence: high.

## AUD-014 - External AI/Vector Runtime Availability Is Not Current-Audit Verified

- Type: `DEPLOYMENT_RISK`
- Severity: `P2`
- Module: model/embedding/vector providers
- Location: `backend/app/core/config.py:49-84,193-258`; provider adapters and runtime settings.
- Discovery: sanitized configuration and no-call boundary audit.
- Evidence: several real-call flags are enabled in the current settings, but external calls were prohibited; OCR/local LLM are disabled.
- Reproduction: requires controlled provider acceptance with explicit authorization.
- Expected: enabled providers have a current health/call result, timeout/fallback evidence and sanitized logs.
- Actual: code/config exist, but availability in this snapshot is unknown.
- Impact: vector/hybrid/model paths may fall back or fail under real workload.
- Root cause: environment-dependent services cannot be established from static code or historical reports.
- Recommendation: run the existing controlled check scripts in a separate authorized acceptance task and freeze sanitized results by configuration hash.
- Suggested test: provider health, one bounded call, schema validation, fallback, timeout and no-secret log checks.
- Fix cost/risk: medium / medium.
- Confidence: high.

## AUD-015 - Legacy/Generated Frontend And Package Naming Create Delivery Ambiguity

- Type: `MAINTAINABILITY_ISSUE`
- Severity: `P3`
- Module: frontend/repository layout
- Location: `frontend/package.json`; `frontend_legacy_before_cupProject_20260611_185550/`; `backend/static/frontend/`.
- Discovery: repository inventory/Git diff.
- Evidence: package name is `cupproject`; legacy source remains; numerous static hashed assets are changed/deleted/untracked.
- Reproduction: inspect root directories and frontend package metadata.
- Expected: one authoritative frontend source and an explicit generated-static policy.
- Actual: multiple plausible frontend/artifact locations remain.
- Impact: operator may package or modify the wrong tree.
- Root cause: frontend merge retained historical naming and backups.
- Recommendation: document/archive the legacy tree outside delivery, rename package metadata and regenerate static assets from the committed source in release automation.
- Suggested test: delete generated artifacts in a clean clone, rebuild, and compare manifest/hash.
- Fix cost/risk: low / low.
- Confidence: high.

## Issue Priorities

Before delivery, address AUD-001 through AUD-006. AUD-007 through AUD-014 should enter the first stabilization sprint. AUD-015 is cleanup but should be resolved before handing the repository to a new team.
