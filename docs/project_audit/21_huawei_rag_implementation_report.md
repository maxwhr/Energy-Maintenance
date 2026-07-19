# Task 27A Huawei SUN2000 RAG Implementation Report

**Date:** 2026-07-16  
**Scope:** Huawei SUN2000 text retrieval and traceable maintenance answers only  
**Delivery status:** `NOT_READY`

## 1. Implementation Boundary

Task 27A converged the formal retrieval path on `huawei_sun2000_competition_v1`. It did not add a migration, provider, embedding, pgvector, OCR, multimodal processing, or a Sungrow retrieval scope. Existing Sungrow data and code were not deleted.

The implementation touch set comprises:

- Backend route/schema: `app/api/routes/retrieval.py`, `app/schemas/query_aware_retrieval.py`, `app/schemas/query_understanding.py`, `app/schemas/retrieval_scope.py`.
- Backend retrieval/answer services: `answer_generation_service.py`, `candidate_hydration_service.py`, `conversation_retrieval_context_service.py`, `deterministic_evidence_rerank_service.py`, `deterministic_query_understanding_service.py`, `multi_query_retrieval_service.py`, `pre_rerank_hard_guard_service.py`, `query_aware_retrieval_service.py`, `query_signal_extraction_service.py`, `query_understanding_merge_service.py`, `retrieval_plan_service.py`, `retrieval_scope_service.py`, and `retrieval_service.py`.
- Frontend: `frontend/src/api/retrieval.ts`, `frontend/src/types/index.ts`, and `frontend/src/views/knowledge/Search.vue`.
- Task scripts/tests: the Task 27A evaluation, diagnostics, database guard, incident inspection, expert material builder, frozen fixture, targeted unit tests, and the safety correction in `test_exact_query_fast_path.py`.

## 2. Formal Scope

The scope is metadata-driven and does not depend on a fixed UUID allow-list. Inclusion requires an active, parsed, approved, current, Chinese Huawei SUN2000 document or directly relevant FusionSolar maintenance evidence with a real source. Chunks must also be active.

The scope excludes Sungrow/SG, LUNA2000, standalone SmartLogger material, pending/draft/rejected/archived records, failed parses, fixtures, seeds, hard negatives, demo-only material, source-less generated content, and unrelated Huawei material.

Read-only PostgreSQL inventory:

| Document | Family | Source type | Status | Chunks | Inclusion reason |
|---|---|---|---|---:|---|
| EDOC1100022346 | SUN2000 | vendor_official | approved/active/parsed | 72 | Official current Chinese SUN2000 maintenance evidence |
| EDOC1100059933 | SUN2000 | vendor_official | approved/active/parsed | 68 | Official current Chinese SUN2000 maintenance evidence |
| EDOC1100083811 | FusionSolar | vendor_official | approved/active/parsed | 15 | Directly relevant SUN2000/FusionSolar evidence |
| EDOC1100253089 | SUN2000 | vendor_official | approved/active/parsed | 77 | Official current Chinese SUN2000 maintenance evidence |
| EDOC1100270192 | SUN2000 | vendor_official | approved/active/parsed | 95 | Official current Chinese SUN2000 maintenance evidence |
| EDOC1100273863 | FusionSolar | vendor_official | approved/active/parsed | 291 | Directly relevant SUN2000/FusionSolar evidence |
| SUN2000 FAQ - WiFi password | SUN2000 | vendor_official_html | approved/active/parsed | 1 | Official SUN2000 FAQ |
| SUN2000 FAQ - no startup | SUN2000 | vendor_official_html | approved/active/parsed | 1 | Official SUN2000 FAQ |
| SUN2000 FAQ - night WiFi | SUN2000 | vendor_official_html | approved/active/parsed | 1 | Official SUN2000 FAQ |

Total: **9 documents / 621 active chunks**. Three FAQ titles contain historical encoding damage in PostgreSQL metadata; their source and chunk eligibility remain traceable. The dry-run repair script proposed zero metadata changes.

## 3. Query Signals

- Manufacturer aliases normalize Huawei/华为 variants to `huawei`.
- `SUN2000`, spaced/case variants, and submodels such as `SUN2000-100KTL-M1` are normalized while retaining the raw form and model confidence.
- Pure numeric alarm extraction is context-guarded and restricted to known Huawei codes. Years, dates, page numbers, voltages, powers, and unrelated numeric sequences do not become alarm codes.
- Finite Chinese terminology covers communication interruption, insulation, temperature/fan, grid, DC input, MPPT, and common maintenance intents without depending on whitespace tokenization.
- A bare `SUN2000` is treated as a product family, not an exact submodel. This prevents generic-family queries from receiving false exact-model protection.

## 4. Retrieval, Answer, And Citations

Both the legacy query path and query-aware path use the same formal competition scope. Query-aware processing follows signals, scope, plan, retrieval, hydration, deterministic reranking, final evidence, existing answer generation, citation validation, and optional persistence.

Answer generation now selects query-relevant, source-diverse excerpts rather than filling all answer points from the first chunk. References are derived from the same final evidence set used for the answer. Unsupported manufacturer/product queries return the formal Huawei SUN2000 support-boundary message with no evidence. Confidence is evidence-dependent and never forced to `1.0`.

R3 retained the same scope and candidate depth. It added general Chinese compound-phrase/proximity scoring, rare-token protection, intent-aware configuration/cause/safety/verification evidence scoring, document-purpose calibration, and evidence-driven sentence/window selection. These rules are derived from the live query and evidence text; they do not inspect case IDs, chunk IDs, document IDs, or evaluation labels. The four missing Top-5 evidence cases now rank 1, 1, 1, and 2 respectively. All five answer-coverage cases retain their required source-supported points.

The evaluator now reports strict lexical and normalized semantic answer-point coverage side by side. The strict metric remains the engineering-gate basis. Normalization is limited to Unicode/case/punctuation/unit normalization, finite synonyms, and bounded action-object matching with exact numeric preservation.

The response contract includes the user answer, suggested steps, safety notes, confidence, references, trace ID, request ID, signals, diagnostics, abstention, persistence status, and message.

## 5. QA Persistence And Safety

- Public query-aware requests default to `persist_result=true`; evaluation, preview, and read-only API probes explicitly use `false`.
- A supplied `request_id` produces a deterministic trace identity. Unit tests cover retry idempotency, rollback, conflict recovery, and zero-write preview behavior.
- Real persistence integration was **not** accepted: `energy_user` has no database-creation privilege, and no isolated database named with `_test` or `task27a` was available. The guarded script correctly refused `energy_maintenance` with `writes_attempted=false`.
- Record Center visibility, concurrent duplicate handling, and one-request/one-record behavior therefore remain unverified against a real isolated PostgreSQL database.
- A pre-existing integration test omitted `persist_result=false` and created one production QA row (`SUN2000-100KTL-M1 通信参数`) during this task. The test was corrected. The row was not deleted because production cleanup was prohibited. Initial QA count was 2597; final count is 2598. Every subsequent evaluation/API probe was read-only and preserved `372 documents / 4791 chunks / 2598 QA records`.

## 6. Frontend

The existing knowledge search page is now the formal Huawei SUN2000 experience. It submits `request_id`, disables real providers, requests persistence for normal user use, and renders answer, steps, safety notes, confidence, trace/request IDs, persistence warnings, references, and collapsible diagnostics. Manufacturer and product scope are fixed to Huawei SUN2000; unsupported-scope, loading, empty, error, abstained, success, and persistence-warning states are represented.

## 7. Verification

- Final R3 targeted backend suite: **84 passed, 319 deselected in 7.82s**.
- Evaluator-normalization boundary tests: **5 passed** as part of the suite; wrong numeric values and unrelated actions remain rejected.
- Backend compile: `uv run python -m compileall app scripts` passed.
- Alembic read-only check: `20260712_0015 (head)`; no revision or upgrade was run.
- Frontend type check: `npm.cmd exec vue-tsc -- --noEmit` passed.
- Temporary frontend build: Vite build passed (1976 modules, 1.88s); formal static assets were not overwritten.
- Final frozen 30-case read-only evaluation: strict engineering gate passed, **0 failed cases / 0 failure events**, and production counts remained `372 documents / 4791 chunks / 2598 QA records`.
- UTF-8 read-only API regression on temporary port 8014 passed seven cases: alarm 103, RS485-2, MPPT multi-peak, energized-cable safety, shutdown verification, Sungrow out-of-scope, and LUNA2000 out-of-scope. In-scope cases surfaced the frozen expected chunk and all strict answer points; out-of-scope cases abstained with zero references; every request returned `skipped_preview`; QA count remained 2598. The temporary instance was stopped.
- Read-only HTTP regression from R2 on port 8013 remains valid: health passed; alarm 103 returned five real references with the labelled chunk first; out-of-scope Sungrow query abstained with zero references; both returned `skipped_preview`.

## 8. Known Limitations

The keyword engineering gate now passes and the original nine frozen failures are fixed without changing the fixture. Overall status remains `NOT_READY` because no isolated PostgreSQL test database could be created by the non-`CREATEDB` application role, so one-request/one-record, retry/concurrent idempotency, rollback, trace uniqueness, and Record Center visibility have not been accepted against a real isolated database. The frozen set also lacks human expert review, Hybrid remains blocked, and the identified production QA incident is still `PENDING_AUTHORIZED_CLEANUP`. Production remained unchanged throughout R3 after the 2598-record baseline, but the earlier Task 27A incident prevents claiming that production was unchanged across the entire Task 27A period.
