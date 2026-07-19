# Task 32A System Regression Acceptance

## 1. Conclusion

Final status: `TASK32A_SYSTEM_FUNCTIONAL_TEST_PASSED`.

Task 32A continued from run `20260719214042`. It did not create a new database, connect to the formal database, execute a migration, run embedding/vector work, invoke a fifth Provider request, or execute Git operations.

## 2. Environment And Scope

- Test database: `energy_maintenance_task32a_test` on the isolated task port 55433.
- Test backend: task-only FastAPI instance on port 8050.
- Existing port 8000 instance: observed only and left untouched.
- Alembic heads/current: `20260712_0015`.
- Covered product areas: auth/RBAC, dashboard, devices, alarms, knowledge lifecycle, RAG/citations, diagnosis preview, multimodal evidence, human confirmation, SOP draft boundary, QA confirm, record center, desktop/mobile UI, security/privacy and performance.
- Explicit exclusions: formal DB, R3G/R3H ranking research, consumed holdout, Task 31A, embedding/vector/DashVector, schema migration, automatic SOP execution and automatic maintenance-task creation.

## 3. Case Statistics

| Metric | Result |
| --- | --- |
| Planned / executed | 37 / 37 |
| Passed / failed | 37 / 0 |
| P0 | 23 / 23 passed |
| P1 | 14 / 14 passed |
| P2 | 0 / 0 |
| Pass rate | 100% |
| Open P0 / P1 defects | 0 / 0 |

The per-case execution ledger is in `docs/project_audit/72_task32a_system_functional_test_plan.md`; machine-readable actuals and evidence paths are in `.runtime/task32a/regression/reconstructed_acceptance_checklist.json`.

## 4. Automated Regression

- Backend compileall: passed.
- Focused regression: 36 passed.
- Product regression: 451 passed, 1 skipped.
- The skipped case remains an intentional environment/optional-capability skip.
- R3G/R3H ranking research, consumed holdout, embedding/vector/DashVector and formal-database tests were explicitly excluded.
- Two citation source-contract tests were updated after validation logic moved into a helper. This was test-contract maintenance, not a product behavior relaxation.

## 5. Frontend And Browser Acceptance

- TypeScript: `vue-tsc --noEmit` passed. There is no standalone `npm run typecheck` script; the production `build` script also runs `vue-tsc -b`.
- Production build: passed.
- Static frontend installation: passed; 82 files copied.
- Desktop: 25 admin routes and 9 viewer routes passed; blank pages and blocking console errors were zero.
- Mobile: 10 required routes passed at a PNG-verified 390 x 844 viewport; no horizontal overflow was detected.
- Mobile interactions included navigation, the knowledge chunk drawer, multimodal confirmation-area scrolling and Record Center detail.
- `/records` initially fell through to Dashboard. Adding it as an alias for the existing `/trace` Record Center route fixed the issue and the mobile browser retest passed.
- No browser Provider action was clicked after the four-call budget was consumed.

## 6. Authentication And RBAC

- Admin, expert, engineer and viewer authentication passed.
- Invalid, anonymous and wrong-credential paths returned controlled errors.
- Admin management/review routes were available.
- Viewer upload, review write, Provider, confirm, SOP and task write controls were hidden.
- Forced viewer access to an admin route redirected to `/403`; direct write API denial was verified and produced no business-data delta.
- Stateless JWT logout is documented as `KNOWN_STATELESS_AUTH_BOUNDARY`, not as an immediate server-side token-revocation guarantee.

## 7. Knowledge Lifecycle, RAG And Citation

- TXT, MD, PDF and DOCX fixtures uploaded, parsed and generated non-empty chunks.
- Pending-review documents were excluded from retrieval; approved active documents participated; archived documents were excluded.
- All 16 Task32A upload/retry fixtures ended archived, with zero active Task32A document residue.
- RAG responses used real document/chunk citations. Non-PDF source locators and strict PDF page/section rules both passed regression.
- Preview produced zero QA/Provider writes in the final performance run.
- Confirm idempotency passed; the two canonical cases produced the intended two QA rows only.
- Record Center desktop/mobile detail and traceability checks passed.

## 8. Multimodal And Provider Results

The Provider budget was exactly 4/4:

- Two OCR calls returned structured results.
- One Vision call returned a structured result.
- One Vision call returned an empty response and was safely downgraded.
- Retry count was zero; no fifth request was sent.
- The empty response is classified as `EXTERNAL_PROVIDER_CONTROLLED_FAILURE`. It is not represented as a successful Provider result.
- Human confirmation remained authoritative, and downstream RAG/citation/QA/SOP-draft workflows remained usable.
- Both canonical multimodal cases ended in `SOP_DRAFT_READY`.
- No automatic maintenance task or SOP execution was created.

## 9. Performance

Final-code performance used eight existing retrieval/case samples and made no Provider call:

| Metric | Result | Gate |
| --- | ---: | ---: |
| P50 | 2285.88 ms | <= 3500 ms |
| P95 | 4098.15 ms | <= 6000 ms |
| QA delta | 0 | 0 |
| Provider log delta | 0 | 0 |

The first sample included cold-start cost, but the frozen P95 acceptance gate still passed.

## 10. Database Reconciliation

The final read-only reconciliation passed against the isolated Task32A database.

| Table | Delta | Classification |
| --- | ---: | --- |
| knowledge_documents | +16 | EXPECTED_TASK32A_TEST_WRITE |
| knowledge_chunks | +16 | EXPECTED_TASK32A_TEST_WRITE |
| knowledge_review_records | +32 | EXPECTED_TASK32A_TEST_WRITE |
| qa_records | +2 | EXPECTED_TASK32A_TEST_WRITE |
| uploaded_media | +4 | EXPECTED_TASK32A_TEST_WRITE |
| multimodal_maintenance_cases | +2 | EXPECTED_TASK32A_TEST_WRITE |
| operation_logs | +107 | EXPECTED_TASK32A_TEST_WRITE (API/browser audit events) |
| external_api_call_logs | +4 | EXPECTED_TASK32A_TEST_WRITE |
| diagnosis_records | 0 | IDEMPOTENT_EXISTING_RECORD |
| maintenance_tasks | 0 | IDEMPOTENT_EXISTING_RECORD |
| sop_execution_records | 0 | IDEMPOTENT_EXISTING_RECORD |
| vector_index_runs | 0 | IDEMPOTENT_EXISTING_RECORD |

No direct SQL business-data modification was used for reconciliation or cleanup. The `alarms` count is not applicable because this schema has no standalone alarms table; alarm definitions are exposed through existing product structures/APIs.

## 11. Security And Privacy

- 71 Task32A evidence/source text files scanned.
- Secret blocking count: 0.
- Privacy blocking count: 0.
- Persisted JWT count: 0.
- Persisted image Base64 count: 0.
- Persisted Provider raw response count: 0.
- The initial static-install failure log contained a local Conda/PATH diagnostic dump. It was replaced by a clean successful `-NoProfile` install log before final scanning.

## 12. Defect Closure

Six reproducible defects were found and closed:

1. Safe absolute upload-directory metadata handling.
2. Non-PDF citation locator validation.
3. Server-side Task32A Provider authorization/call-budget gate.
4. Duplicate full QueryAware retrieval in multimodal orchestration.
5. Excess fast-path query-variant scoring and latency.
6. Missing `/records` Record Center route alias.

Details, reproduction, root cause, files and regressions are in `docs/project_audit/73_task32a_internal_defect_register.md`.

## 13. Final Boundaries

- Migration executed: no.
- Formal database accessed: no.
- Embedding calls: 0.
- Vector rebuilds: 0.
- Cloud LLM calls outside the approved four OCR/Vision attempts: 0.
- Maintenance-task delta: 0.
- SOP-execution delta: 0.
- Git operations: none.

## 14. Task 32B Data Summary

The submission/report-facing stable summary is stored at `.runtime/task32a/regression/task32b_test_report_data_summary.json`. It excludes credentials, approval tokens, private paths, raw Provider responses, formal-database information and internal failure debugging logs.

Recommended screenshots:

- `.runtime/task32a/screenshots/admin-dashboard-desktop.png`
- `.runtime/task32a/screenshots/mobile_dashboard.png`
- `.runtime/task32a/screenshots/mobile_knowledge_search.png`
- `.runtime/task32a/screenshots/mobile_multimodal.png`
- `.runtime/task32a/screenshots/mobile_record_center.png`

## 15. Final Acceptance

All P0 and P1 cases passed, all six Task32A product defects are closed, the Provider boundary remained intact, security/privacy scans passed, P95 met the gate, and forbidden data deltas remained zero. Task 32A is accepted as `TASK32A_SYSTEM_FUNCTIONAL_TEST_PASSED` within the stated isolated-test and external-capability boundaries.

## 16. Environment Cleanup

- Task-only backend port 8050: stopped and released.
- Isolated PostgreSQL port 55433: stopped with `pg_ctl -m fast` and released.
- Existing port 8000: still listening and not modified.
- Windows PostgreSQL service: `Stopped / Disabled`.
- `pg_hba.conf`: restored; SHA-256 equals the task-start backup.
- Isolated test database, sanitized Provider ledger, reports and screenshots were preserved.
