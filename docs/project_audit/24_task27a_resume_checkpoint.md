# Task 27A Resume Checkpoint

## 1. Resume Scope

This checkpoint records the exact continuation state for Task 27A-R2. The task remains limited to delivery-grade Huawei SUN2000 text retrieval-augmented maintenance QA. It does not start a new feature phase, perform broad refactoring, package delivery artifacts, or enable external model, OCR, embedding, pgvector, Neo4j, Docker, or SQLite capabilities.

## 2. Completed Before This Checkpoint

- Added the unified `huawei_sun2000_competition_v1` retrieval scope and wired it into the formal query-aware retrieval path.
- Added Huawei manufacturer aliases, SUN2000/FusionSolar product-family recognition, SUN2000 model normalization, alarm-code extraction safeguards, fault-category extraction, and canonical symptom handling.
- Added exact model/alarm evidence protection and deterministic candidate filtering so unrelated chunks cannot become formal references.
- Replaced fixed no-evidence wording with Huawei SUN2000-specific abstention text.
- Added preliminary query-aware QA persistence support with deterministic trace IDs when a request ID is supplied, rollback handling, and unique-trace conflict recovery.
- Preserved `persist_result=false` for read-only probes.
- Performed read-only production inventory checks against PostgreSQL on the current native development port. The formal scope resolved to 9 active, parsed, approved, current Chinese Huawei SUN2000/FusionSolar documents and 621 active chunks.
- Read-only probes verified that WiFi communication, insulation-resistance, and over-temperature questions can return real Huawei references, while alarm code 2061 safely abstains when no matching approved chunk exists.
- Existing query-signal unit tests passed before this checkpoint.

## 3. Files Already Modified And To Be Continued

- `backend/app/api/routes/retrieval.py`
- `backend/app/schemas/query_aware_retrieval.py`
- `backend/app/schemas/query_understanding.py`
- `backend/app/schemas/retrieval_scope.py`
- `backend/app/services/answer_generation_service.py`
- `backend/app/services/candidate_hydration_service.py`
- `backend/app/services/conversation_retrieval_context_service.py`
- `backend/app/services/deterministic_evidence_rerank_service.py`
- `backend/app/services/deterministic_query_understanding_service.py`
- `backend/app/services/multi_query_retrieval_service.py`
- `backend/app/services/query_aware_retrieval_service.py`
- `backend/app/services/query_signal_extraction_service.py`
- `backend/app/services/query_understanding_merge_service.py`
- `backend/app/services/retrieval_plan_service.py`
- `backend/app/services/retrieval_scope_service.py`
- `backend/app/services/retrieval_service.py`

## 4. Known Defects Or Incomplete Work

- The query-aware response still needs an explicit `request_id` field.
- Unsupported first-version scope queries such as Sungrow, LUNA2000, and standalone SmartLogger need a pre-retrieval guard with a clear Huawei SUN2000 support-boundary message.
- QA persistence diagnostics need to retain the request ID and sanitized retrieval-candidate identifiers.
- Request retry and concurrent duplicate behavior need targeted isolated-database tests.
- Query signals need an explicit exact-model confidence indicator or equivalent documented field and broader negative numeric tests.
- A dry-run-only, idempotent metadata repair utility and its safety checks are not yet implemented.
- The formal 9-document inventory still needs per-document chunk counts and inclusion reasons in the final report.
- The isolated Task 27A PostgreSQL test database has not yet been created or migrated.
- The frontend Huawei formal-answer presentation has not yet been completed.
- The frozen 30-case engineering-candidate evaluation dataset, baseline metrics, failure analysis, and acceptance JSON have not yet been created.
- Final targeted regression, temporary frontend production build, and isolated API verification remain outstanding.

## 5. Errors Found And Already Corrected

- Fixed an undefined stage variable in the query-aware retrieval orchestration.
- Prevented insulation-resistance queries from citing unrelated WiFi FAQ chunks by adding canonical symptom matching and signal-supported evidence retention.
- Preserved scalar query facts through deterministic understanding, merge, and conversation-context stages.
- Prevented query-aware read-only probes from persisting conversations or QA records when `persist_result=false`.

## 6. Files And Areas Not To Modify

- Existing Alembic migrations unless a proven schema defect requires an explicitly approved change. No migration is currently planned for Task 27A-R2.
- External API, OCR, multimodal, agent-runtime, knowledge-graph, pgvector, embedding, and model-provider modules.
- Delivery archives, `delivery/`, `delivery_staging/`, or packaging scripts.
- Production upload files and existing formal database records.
- Unrelated dirty-worktree files from previous tasks.

## 7. Database Safety Boundary

- The production database `energy_maintenance` is read-only for Task 27A verification, except normal public behavior explicitly tested with `persist_result=false`; no production QA write is allowed during this continuation.
- No `alembic upgrade head` will run against `energy_maintenance`.
- Before and after production document, chunk, and QA counts will be recorded with `SELECT` queries.
- Persistence tests may run only in a separately named database containing `_test` or `task27a`, after an explicit database-name guard passes.
- If the current PostgreSQL role cannot create an isolated database, write-path acceptance will be reported as blocked rather than redirected to production.

## 8. Next Execution Steps

1. Finish response, unsupported-scope, query-signal, and QA idempotency fixes.
2. Add scope, signal, persistence, and evidence-integrity targeted tests.
3. Add the dry-run metadata repair utility and generate the formal document inventory.
4. Attempt guarded isolated PostgreSQL database creation and run migrations and persistence tests there only.
5. Complete the existing retrieval page's formal Huawei answer states without broad UI redesign.
6. Create and execute the frozen 30-case keyword baseline evaluation.
7. Run targeted backend tests, compile checks, isolated API smoke, frontend type check, and temporary production build.
8. Produce Task 27A implementation, evaluation, failure-case, and machine-readable acceptance reports with an honest READY status ceiling of `READY_WITH_FIXES` until human expert review is completed.

## 9. Final Continuation Outcome

Task 27A-R2 continued from this checkpoint and completed the remaining engineering work and reporting without starting a new feature task.

- Final status: `NOT_READY`.
- Formal scope: 9 documents / 621 active chunks.
- Frozen evaluation: 30 engineering-candidate cases; human expert review remains blocked.
- Final keyword result: Recall@1 0.535714, Recall@3 0.821429, Recall@5 0.857143, MRR 0.667857, nDCG@5 0.715768.
- Failed cases: 9; failure events: 17.
- Targeted backend regression: 52 passed.
- Frontend type check and temporary production build: passed.
- Read-only API regression: passed with `persist_result=false`; unsupported scope abstained correctly.
- Isolated PostgreSQL persistence integration: blocked because the current role cannot create a safely named test database.
- Production safety finding: one existing integration test wrote one QA row before its missing `persist_result=false` guard was corrected. No cleanup was performed.
- Hybrid evaluation: blocked and not executed.

The final evidence is recorded in reports 21, 22, 23, and `huawei_rag_acceptance.json`. The earlier incomplete-work list above is retained as historical checkpoint context rather than rewritten after the fact.
