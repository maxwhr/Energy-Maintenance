# Task 32A Internal Defect Register

This is an internal engineering artifact. It is not a submission-facing software test report.

| defect_id | module | priority | symptom | reproduction | root_cause | affected_files | fix_summary | regression_test | final_status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| TASK32A-DEF-001 | knowledge upload | P0 | A valid project-external absolute upload directory could not be persisted correctly | Upload a TXT fixture with an approved absolute `UPLOAD_DIR` outside `backend` | Path metadata assumed every upload directory was relative to backend | `backend/app/services/knowledge_service.py` | Preserve safe relative paths inside backend and normalized absolute paths outside it while retaining containment checks | `backend/tests/unit/test_knowledge_upload_path.py`; focused and product suites | CLOSED |
| TASK32A-DEF-002 | citation | P0 | TXT/MD/DOCX source locators were evaluated as if they were PDF locators | Build citations for non-PDF parsed documents | File-type-specific locator validation was embedded in the PDF-oriented path | `backend/app/services/citation_validation_service.py`; `backend/app/services/citation_batch_builder_service.py` | Added a shared source-locator validator that preserves strict PDF page/section requirements and allows real non-PDF document/chunk locators | citation builder, scope and HTML/source-contract tests | CLOSED |
| TASK32A-DEF-003 | provider safety | P0 | Task32A provider authorization existed at script level but lacked an equivalent server-side hard gate | Attempt a fifth real call or use a non-target database | Gateway did not recognize the complete Task32A authorization boundary | `backend/app/services/external_api_gateway.py` | Added database, call-budget, embedding/vector/Git and authorization checks before network dispatch | `backend/tests/test_task32a_provider_gate.py` and 17 provider-gate assertions | CLOSED |
| TASK32A-DEF-004 | multimodal retrieval | P1 | A case `/retrieve` operation repeated the complete QueryAware retrieval path | Retrieve either canonical Task32A multimodal case | Orchestration independently requested equivalent retrieval results for downstream answer/citation work | `backend/app/services/multimodal_case_orchestrator_service.py` | Execute QueryAware retrieval once per case operation and reuse the grounded result | `backend/tests/unit/test_multimodal_retrieve_single_pass.py`; focused/product regression | CLOSED |
| TASK32A-DEF-005 | RAG performance | P1 | Fast-path retrieval scored the same scope across three query variants and exceeded the intended latency budget | Run the original fast-path performance probe | Fast-path did not cap deduplicated query variants | `backend/app/services/retrieval_plan_service.py` | Limit fast-path to the first two deduplicated variants while preserving original/canonical query semantics; deep path unchanged | `backend/tests/unit/test_fast_path_query_budget.py`; final P95 4098.15 ms | CLOSED |
| TASK32A-DEF-006 | frontend routing | P1 | Direct mobile navigation to `/records` fell through to Dashboard instead of Record Center | Open `/records` in a fresh authenticated browser context | Record Center existed at `/trace` but had no compatibility alias | `frontend/src/router/index.ts` | Added `/records` as an alias of the existing Record Center route | production build plus 390 x 844 browser route verification | CLOSED |

Defects are added only after reproduction. Failures that require schema changes, formal-database changes, new external services, Task 31A, or ranking research are recorded as `TASK32A_BLOCKED_REQUIRES_SEPARATE_AUTHORIZATION` and are not implemented in this task.

## Controlled Boundaries (Not Product Defects)

- `EXTERNAL_PROVIDER_CONTROLLED_FAILURE`: one approved Vision attempt returned an empty response. It was not retried, no result was fabricated, and human confirmation/downstream business flow remained available.
- `KNOWN_STATELESS_AUTH_BOUNDARY`: JWT logout is client-side/stateless and does not promise immediate server-side token revocation. Invalid and expired tokens are still rejected.
- Citation source-contract tests were updated to inspect the extracted validator helper after DEF-002. This was a test-contract maintenance change, not an additional product defect.

Final totals: 6 defects found, 6 closed, open P0 = 0, open P1 = 0.
