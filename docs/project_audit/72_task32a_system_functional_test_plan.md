# Task 32A System Functional Test Plan

## 1. Scope And Safety Gates

- Approval: `APPROVE_TASK32A_FULL_SYSTEM_TEST_AND_FIX_V1` is present in the user authorization.
- Database writes: only `energy_maintenance_task32a_test` on `127.0.0.1:55433`.
- Clone source: prefer `energy_maintenance_task28a_r3i_test`, otherwise `energy_maintenance_task27a_test`.
- Backend: task-only instance on `127.0.0.1:8050`; the existing port 8000 instance is not changed.
- Real OCR/Vision budget: at most four network attempts, at most one per approved test-image class.
- Forbidden: formal database access, schema/Alembic changes, embedding/vector rebuild, consumed holdout, Task 31A, ranking changes, automatic SOP execution, automatic maintenance-task creation, Git operations, and secret persistence.

## 2. Execution Policy

Every P0 and P1 case is executed. P2 cases are executed where they are required for browser, responsive-layout, security, and stability acceptance. A failed case remains in the register until its root cause is identified, a focused regression is added when code changes are required, and the full applicable suite passes.

Preview requests use `persist_result=false`, `enable_llm=false`, `allow_real_api=false`, and `enable_vector=false`. Provider-error cases use local mocks and do not consume the real-call budget. Real provider attempts are counted before dispatch and are never automatically retried.

## 3. Test Cases

| case_id | module | priority | precondition | steps | expected_result | execution_type | result | evidence_path |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T32-SYS-001 | startup | P0 | isolated DB available | start backend; request health/OpenAPI/root/login | all endpoints respond and static assets load | automated + browser | passed | `.runtime/task32a/backend/` |
| T32-SYS-002 | startup | P1 | backend running | stop and restart task backend | service recovers without data loss | automated | passed | `.runtime/task32a/regression/` |
| T32-AUTH-001 | auth | P0 | four role fixtures | log in as admin/expert/engineer/viewer | valid credentials return role-correct sessions | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-AUTH-002 | auth | P1 | login page | submit wrong/blank credentials; logout; refresh | controlled error, token cleared, redirect safe | browser | passed | `.runtime/task32a/browser/` |
| T32-RBAC-001 | RBAC | P0 | all roles authenticated | exercise protected read/write APIs | backend permissions match role policy | automated | passed | `.runtime/task32a/regression/` |
| T32-RBAC-002 | RBAC | P1 | viewer session | inspect menus/buttons and force write routes | write controls hidden and API returns 403 | browser + automated | passed | `.runtime/task32a/browser/` |
| T32-DASH-001 | dashboard | P0 | seeded test DB | open dashboard and query statistics | real statistics render without API failure | browser + automated | passed | `.runtime/task32a/screenshots/` |
| T32-DEV-001 | devices | P1 | seeded devices | list/search/filter/paginate/open detail | expected devices and models render | browser + automated | passed | `.runtime/task32a/browser/` |
| T32-ALARM-001 | alarms | P1 | seeded alarms | list/search/filter/open alarm | expected alarm data and status render | browser + automated | passed | `.runtime/task32a/browser/` |
| T32-DIAG-001 | diagnosis | P0 | Huawei corpus active | submit diagnosis preview | causes, safety, evidence and citations return; zero persistent delta | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-KNOW-001 | knowledge | P0 | admin/expert | upload TXT/MD/PDF/DOCX fixtures | parse succeeds, chunks are non-empty, status pending review | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-KNOW-002 | knowledge | P0 | pending document | search before/after approval and after archive | pending/archived excluded; approved active included | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-KNOW-003 | knowledge | P1 | upload endpoint | submit duplicate, empty, unsupported, bad name and oversize files | current duplicate policy is honored; unsafe files rejected | automated | passed | `.runtime/task32a/security/` |
| T32-KNOW-004 | knowledge | P1 | document exists | inspect detail/chunks/source/review and reparse | data remains consistent and scope cache refreshes | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-RAG-001 | retrieval | P0 | approved Huawei corpus | query model/parameter/alarm/communication/insulation/grid/Amphenol | grounded answer and real citations return | automated + browser | passed | `.runtime/task32a/performance/` |
| T32-RAG-002 | retrieval | P0 | safe baseline | query no-answer, insufficient, dangerous and cross-vendor cases | controlled abstention/safety; Huawei query has zero Sungrow citations | automated | passed | `.runtime/task32a/regression/` |
| T32-RAG-003 | retrieval | P0 | preview request | compare QA/diagnosis/task/provider/vector counts | all preview deltas are zero | automated | passed | `.runtime/task32a/database/` |
| T32-QA-001 | QA confirm | P0 | valid preview | confirm twice with same request id | one QA row, unique trace, duplicate produces no write | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-CITE-001 | citation | P0 | retrieval result | open every returned citation | document/chunk exists and content is non-empty/traceable | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-MM-001 | multimodal | P0 | four private-free test images | upload and invoke one OCR/Vision call per class | structured auxiliary evidence; call budget <= 4 | automated + browser | passed | `.runtime/task32a/provider/` |
| T32-MM-002 | multimodal | P0 | provider evidence exists | accept/edit/reject/request retake/confirm | human values are authoritative and audit events retained | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-MM-003 | multimodal | P0 | confirmed evidence | run Huawei RAG, diagnosis preview, SOP draft, QA preview/confirm | citations valid; safe boundaries and idempotency hold | automated + browser | passed | `.runtime/task32a/regression/` |
| T32-MM-004 | multimodal | P1 | viewer session | open cases and attempt write/provider actions | readable fields remain available; writes blocked | automated + browser | passed | `.runtime/task32a/browser/` |
| T32-SOP-001 | SOP | P0 | confirmed evidence | create draft only | draft returned; no execution record | automated + browser | passed | `.runtime/task32a/database/` |
| T32-TASK-001 | tasks | P0 | all previews | compare maintenance task counts | no automatic task is created | automated | passed | `.runtime/task32a/database/` |
| T32-REC-001 | record center | P0 | one confirmed QA | list/detail/search/filter/timeline/citations | confirmed record appears once; no private fields | automated + browser | passed | `.runtime/task32a/browser/` |
| T32-USR-001 | users | P1 | admin/viewer sessions | list users and test management visibility | admin allowed; viewer management blocked | automated + browser | passed | `.runtime/task32a/browser/` |
| T32-ERR-001 | error handling | P1 | test backend | exercise 403/404/expired token/API error | controlled messages, no stack or secret leakage | automated + browser | passed | `.runtime/task32a/security/` |
| T32-ERR-002 | provider errors | P1 | mock adapters | disabled/timeout/empty/invalid JSON/allow_real_api=false | controlled state, no fallback or unexpected write | automated | passed | `.runtime/task32a/regression/` |
| T32-SEC-001 | upload security | P0 | crafted fixtures | test traversal, illegal names, content type, size, EXIF/privacy | no path escape or private image dispatch | automated | passed | `.runtime/task32a/security/` |
| T32-SEC-002 | secret scanning | P0 | test artifacts created | scan runtime reports/logs and tracked source patterns | no key/JWT/password/header/base64/raw response leak | automated | passed | `.runtime/task32a/security/` |
| T32-PERF-001 | performance | P1 | warmed backend | measure login/search/RAG/citation/record center | RAG P95 <= 6000 ms; metrics recorded | automated | passed | `.runtime/task32a/performance/` |
| T32-STAB-001 | stability | P1 | backend running | repeat refresh/login/logout/preview/confirm and inspect processes | no resource leak, duplicates, or stuck requests | automated + browser | passed | `.runtime/task32a/performance/` |
| T32-UI-001 | desktop browser | P0 | admin session | visit all core routes and use primary controls | no blank pages, blocking console/API/static failures | browser | passed | `.runtime/task32a/screenshots/` |
| T32-UI-002 | mobile browser | P1 | 390x844 viewport | visit login/dashboard/retrieval/knowledge/multimodal/records | no horizontal overflow or unusable control | browser | passed | `.runtime/task32a/screenshots/` |
| T32-DATA-001 | data integrity | P0 | test complete | compare before/after counts and tagged writes | only authorized test deltas; vector/SOP execution/unexpected task deltas zero | automated | passed | `.runtime/task32a/database/` |
| T32-ALEMBIC-001 | migration guard | P0 | isolated DB | read current/head only | both equal `20260712_0015`; no migration executed | automated | passed | `.runtime/task32a/database/` |

## 4. Acceptance Gates

Task 32A may be marked passed only when every P0/P1 row above is executed and passed, reproducible P0/P1 defects are closed, browser blocking errors and core API failures are zero, the real-provider call count is no more than four, all write deltas are authorized and traceable, no formal database connection occurs, and Alembic remains `20260712_0015` without migration execution.

## 5. Final Execution Ledger

The original plan was executed without deleting or downgrading any case. Detailed actual results and evidence arrays are preserved in `.runtime/task32a/regression/reconstructed_acceptance_checklist.json`.

| case_id | executed | result | defect_id | regression_status |
| --- | --- | --- | --- | --- |
| T32-SYS-001 | yes | passed | - | passed |
| T32-SYS-002 | yes | passed | - | passed |
| T32-AUTH-001 | yes | passed | - | passed |
| T32-AUTH-002 | yes | passed | - | passed |
| T32-RBAC-001 | yes | passed | - | passed |
| T32-RBAC-002 | yes | passed | - | passed |
| T32-DASH-001 | yes | passed | - | passed |
| T32-DEV-001 | yes | passed | - | passed |
| T32-ALARM-001 | yes | passed | - | passed |
| T32-DIAG-001 | yes | passed | - | passed |
| T32-KNOW-001 | yes | passed | TASK32A-DEF-001 | passed after fix |
| T32-KNOW-002 | yes | passed | - | passed |
| T32-KNOW-003 | yes | passed | TASK32A-DEF-001 | passed after fix |
| T32-KNOW-004 | yes | passed | - | passed |
| T32-RAG-001 | yes | passed | TASK32A-DEF-005 | passed after fix |
| T32-RAG-002 | yes | passed | - | passed |
| T32-RAG-003 | yes | passed | - | passed |
| T32-QA-001 | yes | passed | - | passed |
| T32-CITE-001 | yes | passed | TASK32A-DEF-002 | passed after fix |
| T32-MM-001 | yes | passed | TASK32A-DEF-003 | passed after fix; one controlled external empty response |
| T32-MM-002 | yes | passed | - | passed |
| T32-MM-003 | yes | passed | TASK32A-DEF-004 | passed after fix |
| T32-MM-004 | yes | passed | - | passed |
| T32-SOP-001 | yes | passed | - | passed |
| T32-TASK-001 | yes | passed | - | passed |
| T32-REC-001 | yes | passed | - | passed |
| T32-USR-001 | yes | passed | - | passed |
| T32-ERR-001 | yes | passed | - | passed |
| T32-ERR-002 | yes | passed | - | passed |
| T32-SEC-001 | yes | passed | - | passed |
| T32-SEC-002 | yes | passed | - | passed |
| T32-PERF-001 | yes | passed | TASK32A-DEF-004, TASK32A-DEF-005 | passed after fix |
| T32-STAB-001 | yes | passed | - | passed |
| T32-UI-001 | yes | passed | - | passed |
| T32-UI-002 | yes | passed | TASK32A-DEF-006 | passed after fix |
| T32-DATA-001 | yes | passed | - | passed |
| T32-ALEMBIC-001 | yes | passed | - | passed |

## 6. Final Statistics

- Planned: 37
- Executed: 37
- Passed: 37
- Failed: 0
- P0: 23 / 23 passed
- P1: 14 / 14 passed
- P2: 0 / 0 (no P2 cases were present in the frozen plan)
- Overall pass rate: 100%
- Focused automated regression: 36 passed
- Product regression: 451 passed, 1 skipped
- Desktop browser: 25 admin routes and 9 viewer routes
- Mobile browser: 10 required routes at a verified 390 x 844 viewport
- Open P0/P1 defects: 0
