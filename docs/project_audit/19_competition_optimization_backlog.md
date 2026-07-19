# Competition Optimization Backlog

Audit date: 2026-07-16

## Prioritization Rule

Items are ordered by competition capability loss, demo failure probability, answer correctness/safety, knowledge-update closure, and then maintainability. Each item is intentionally narrow enough for one Codex task. No item authorizes production data mutation without a reviewed script, backup and dry-run.

## 1. T26B-RAG-SCOPE - Repair The Dual-vendor Production Retrieval Scope

- Classification: `MUST_FIX_BEFORE_DELIVERY`.
- Feature: Text RAG, corpus eligibility and manufacturer scope.
- Current evidence: legacy default retrieval has 63 Huawei documents/1,393 chunks but 0 Sungrow documents/chunks; query-aware fixed pilot has 16 Huawei documents/1,262 chunks, includes LUNA2000/SmartLogger, and has 0 Sungrow documents.
- Current status: `BROKEN`, L2 for the Sungrow production path.
- User-visible impact: a user can select or ask about Sungrow SG equipment but receive no Sungrow source or an unrelated Huawei result.
- Competition score impact: critical failure of the explicit dual-manufacturer requirement and source-traceability claim.
- Root cause: missing Sungrow normalized-language/default-retrieval metadata plus a fixed Huawei-only query-aware scope.
- Minimum change: define one competition production scope restricted to approved/active Huawei SUN2000/FusionSolar and Sungrow SG documents; add an idempotent dry-run metadata remediation for eligible Sungrow documents; remove LUNA2000/SmartLogger from the default competition scope without deleting data.
- Likely files: `backend/app/services/retrieval_scope_service.py`, `backend/app/services/retrieval_pilot_service.py`, `backend/app/repositories/retrieval_repository.py`, scope seed/maintenance script, targeted tests.
- Database migration: no schema migration expected; reviewed metadata/data maintenance only.
- Vector regeneration: only affected eligible Sungrow/current-scope documents if the vector path is used; no full rebuild.
- Real provider required: no for keyword acceptance; yes only for separately verifying vector mode.
- Expected metric improvement: manufacturer filter accuracy and Sungrow Recall@5 from structurally zero to measurable/passable; manufacturer contamination reduced.
- Change risk: medium, because scope changes can expose archived, pending or out-of-version evidence if filters are wrong.
- Regression tests: approval/archive/version/language filters; Huawei and Sungrow positive cases; LUNA2000/SmartLogger exclusion; empty-scope fallback.
- Acceptance criteria: both public retrieval paths can return real approved Huawei and Sungrow sources, and cannot return pending/archived/out-of-scope documents.
- Recommended sequence: 1.

## 2. T26C-QUERY-SIGNALS - Add Sungrow, Numeric Code And Chinese Fault Signals

- Classification: `MUST_FIX_BEFORE_DELIVERY`.
- Feature: Query understanding and exact-signal protection.
- Current evidence: query-aware extraction misses `SG110CX`, numeric-only `2061`, manufacturer aliases and typo `通迅`; MPPT/communication phrases are weak.
- Current status: `PARTIAL`, L2.
- User-visible impact: concise field queries fail even when matching evidence exists.
- Competition score impact: high impact on model/code Top-1, Recall@5, manufacturer filtering and answer correctness.
- Root cause: model/code regular expressions and domain dictionaries were built around selected Huawei identifiers and prefixed alarm codes.
- Minimum change: add first-class manufacturer signals, SG-series patterns, numeric-only alarm-code rules with context guards, case/hyphen normalization, MPPT/communication mappings and a bounded typo dictionary; preserve existing English matching.
- Likely files: `backend/app/services/query_signal_extraction_service.py`, `backend/app/services/deterministic_query_understanding_service.py`, `backend/app/services/deterministic_query_expansion_service.py`, focused unit tests.
- Database migration: no.
- Vector regeneration: no.
- Real provider required: no.
- Expected metric improvement: exact-model accuracy above zero on the representative set; higher alarm-code Top-1 and manufacturer filter accuracy.
- Change risk: medium; unrestricted numeric matching could treat voltages, years or page numbers as fault codes.
- Regression tests: the eleven Task 26A query forms, including model-only, code-only, typo, mixed manufacturer/model/symptom and off-domain numbers.
- Acceptance criteria: `SG110CX`, `SUN2000`, contextual `2061`, Huawei/Sungrow aliases and communication typo normalize into explicit signals and affect filtering/ranking.
- Recommended sequence: 2.

## 3. T26D-QA-CLOSURE - Complete Query-aware Answer And QA Persistence

- Classification: `MUST_FIX_BEFORE_DELIVERY`.
- Feature: Answer generation, citations, QA record and trace.
- Current evidence: the frontend primary search calls query-aware search; that service returns evidence/debug structures but no user-oriented answer and creates no `qa_records` row. The legacy endpoint has the required answer/persistence behavior.
- Current status: `PARTIAL`, L3.
- User-visible impact: the strongest retrieval path is not a complete maintenance QA workflow and cannot be audited through the record center.
- Competition score impact: high for usability, answer completeness and traceability.
- Root cause: two retrieval generations were integrated in parallel without converging on one response/persistence contract.
- Minimum change: reuse existing rule-based answer, citation validation, safety/abstention and record repository services after query-aware retrieval; return answer/suggested steps/confidence/trace and persist one QA row without changing the public prefix.
- Likely files: `backend/app/services/query_aware_retrieval_service.py`, `backend/app/services/retrieval_service.py`, `backend/app/repositories/record_repository.py`, `backend/app/schemas/query_aware_retrieval.py`, `frontend/src/views/knowledge/Search.vue`, tests.
- Database migration: no if existing QA JSON/trace fields are reused.
- Vector regeneration: no.
- Real provider required: no; deterministic answer is acceptable for closure.
- Expected metric improvement: QA persistence coverage to 100% of successful query-aware requests; answer/citation trace coverage to 100%.
- Change risk: medium; duplicate QA rows and inconsistent trace IDs are the main risks.
- Regression tests: no-result, single/multiple citations, archived citation rejection, transaction rollback and record-center retrieval.
- Acceptance criteria: one query-aware request yields one user answer, real citations, confidence below 1.0, unique trace ID and exactly one matching QA record.
- Recommended sequence: 3.

## 4. T26E-RAG-BENCHMARK - Freeze A Representative Expert-reviewed 30-case Set

- Classification: `MUST_FIX_BEFORE_DELIVERY`.
- Feature: RAG quality evaluation.
- Current evidence: 2,540 cases and four runs exist, but only one case is expert-verified; the sole frozen 30-case set is engineering-controlled and not expert-verified. Stored strong and broad results conflict sharply.
- Current status: `PARTIAL`, L3.
- User-visible impact: quality regressions cannot be distinguished from benchmark artifacts.
- Competition score impact: critical for credible evidence and for avoiding unsafe blind tuning.
- Root cause: accumulated historical/generic cases without a single current dual-vendor competition acceptance contract.
- Minimum change: curate and expert-review 12 Huawei, 12 Sungrow and 6 boundary cases with expected evidence, answer points, prohibited claims, abstention and safety labels; freeze a version before tuning.
- Likely files: an audit/evaluation fixture under `docs/project_audit/evaluation_cases/`, existing retrieval evaluation seed/import script, evaluation documentation; no production knowledge insertion.
- Database migration: no.
- Vector regeneration: no.
- Real provider required: no for dataset construction; provider-specific runs are separate.
- Expected metric improvement: not applicable initially; produces trustworthy Recall@1/3/5, MRR, nDCG@5, manufacturer/model/code, citation, abstention and latency baselines.
- Change risk: low; expert labels must avoid copying protected manual passages.
- Regression tests: schema validation, manufacturer/fault coverage counts, duplicate detection and freeze immutability.
- Acceptance criteria: 30 unique expert-reviewed cases, required category counts, immutable version ID and a reproducible baseline report.
- Recommended sequence: 4, before weight/model tuning.

## 5. T26F-SUNGROW-CORPUS - Fill Specific Sungrow Evidence Gaps

- Classification: `MUST_FIX_BEFORE_DELIVERY`.
- Feature: Knowledge corpus quality.
- Current evidence: only 15 approved active Sungrow documents/102 chunks exist; the two sampled controlled documents contain eight short synthetic chunks each and no Sungrow document is production-eligible.
- Current status: `PARTIAL`, L2 for representative Sungrow evidence.
- User-visible impact: SG temperature, MPPT, communication, insulation, grid and alarm-code questions have weak or absent support.
- Competition score impact: high for the second required manufacturer.
- Root cause: controlled test snippets exist, but representative approved manual/alarm/fault/SOP evidence is incomplete or not normalized.
- Minimum change: ingest a reviewed set targeted to the frozen benchmark gaps: one SG operation manual section set, one alarm-code reference, one safety/maintenance procedure and at least two real fault cases; record manufacturer/product series/model/source and review status.
- Likely files: approved sample/import manifests and existing upload/review APIs; no parser rewrite.
- Database migration: no.
- Vector regeneration: only newly approved Sungrow chunks if vector mode is accepted.
- Real provider required: no for keyword; embedding only for vector acceptance.
- Expected metric improvement: Sungrow Recall@5, answer-point coverage and citation support on the frozen set.
- Change risk: medium; copyright, duplicate versions and uncontrolled test snippets must be managed.
- Regression tests: duplicate/version detection, parse/chunk integrity, review exclusion and source trace.
- Acceptance criteria: every Sungrow benchmark question has at least one expert-approved supporting chunk and no controlled hard-negative document is treated as authoritative evidence.
- Recommended sequence: 5.

## 6. T26G-CORRECTION-CONVERSION - Feed Accepted Corrections Into Reviewed Knowledge

- Classification: `MUST_FIX_BEFORE_DELIVERY`.
- Feature: Model answer annotation and manual correction.
- Current evidence: 15 corrections exist and eight are accepted, but every `converted_contribution_id` is null; no correction-to-contribution/document path was found.
- Current status: `NOT_FOUND` for the feedback-to-knowledge step, making the overall feature `PARTIAL`, L2.
- User-visible impact: experts correct an answer, but later users cannot benefit from the accepted correction.
- Competition score impact: critical because the competition explicitly requires experience accumulation/model correction.
- Root cause: correction review stops at acceptance and is not connected to the existing contribution review/conversion workflow.
- Minimum change: add an explicit expert/admin action that creates a draft knowledge contribution from an accepted correction, links both records, and requires the normal contribution approval before document/chunk creation; never auto-publish.
- Likely files: `backend/app/services/correction_service.py`, contribution service/repository, correction/contribution routes and schemas, `frontend/src/api/corrections.ts`, correction detail view, tests.
- Database migration: probably no; `converted_contribution_id` already exists, subject to relationship verification.
- Vector regeneration: only after the derived contribution is approved and converted; incremental only.
- Real provider required: no.
- Expected metric improvement: accepted-correction conversion coverage from 0% to 100% for explicitly converted items; later retrieval regression demonstrates reuse.
- Change risk: high if acceptance bypasses knowledge review or overwrites original output.
- Regression tests: source QA preserved, roles, duplicate conversion, rejection, contribution approval, archive and later retrieval.
- Acceptance criteria: accepted correction -> linked draft contribution -> expert approval -> real document/chunks -> later query retrieves it, while original answer and all actors remain traceable.
- Recommended sequence: 6.

## 7. T26H-MULTIMODAL-ACCEPTANCE - Verify Four Controlled Image Classes With Current Providers

- Classification: `MUST_FIX_BEFORE_DELIVERY` for a live multimodal claim; otherwise the feature must be presented as a persisted-case demo only.
- Feature: Multimodal fault image retrieval.
- Current evidence: 414 media, 88 OCR results, 133 analyses and 27 cases exist, but current OCR/MIMO provider rows are blocked/disabled and the frontend explicitly defaults to `allow_real_api: false`; 14 evidence conflicts are open.
- Current status: `BLOCKED` for current live inference, overall `PARTIAL`, L3.
- User-visible impact: a newly uploaded alarm screen/nameplate/app screenshot/component photo may not produce live structured evidence.
- Competition score impact: critical for the multimodal premise if live upload is demonstrated.
- Root cause: current provider availability and controlled acceptance are not established, although orchestration is implemented.
- Minimum change: configure one authorized OCR/vision route outside source control, run exactly four sanitized acceptance images, verify extracted model/code/phenomenon, user correction, retrieval citations, failure fallback and stored trace; do not broaden providers.
- Likely files: acceptance script/report and environment-local provider configuration; code changes only for defects found by the bounded run.
- Database migration: no expected.
- Vector regeneration: no.
- Real provider required: yes.
- Expected metric improvement: four-class workflow success, extraction field accuracy, fallback success and trace completeness become measurable.
- Change risk: medium for cost/privacy; test images must be sanitized and call count capped.
- Regression tests: provider blocked, timeout, invalid image, user rejection, conflict handling and no automatic formal work order.
- Acceptance criteria: all four image classes complete the controlled chain or return explicit safe fallback; no fabricated OCR/vision output; all citations and records are traceable.
- Recommended sequence: 7, after text scope is fixed.

## 8. T26I-KG-GROUNDING - Repair Production Evidence Eligibility For Reviewed Graph Facts

- Classification: `SHOULD_OPTIMIZE_BEFORE_DELIVERY`.
- Feature: Knowledge graph participation in retrieval/diagnosis.
- Current evidence: 34 active nodes/34 active edges exist, but the production-scope service accepts 0 nodes, 0 edges and 0 grounded evidence; all 76 evidence links are excluded for `language_en`, with some also archived.
- Current status: `BROKEN`, L2 for production-grounded KG use.
- User-visible impact: graph pages render, but graph context does not enhance production retrieval or diagnosis.
- Competition score impact: medium; contribution workflow already works, but the advertised KG enhancement is not deliverable.
- Root cause: demo-seed evidence metadata/current-version links do not satisfy production quality gates.
- Minimum change: select a small set of expert-reviewed Huawei/Sungrow facts, relink them to current approved Chinese documents/chunks, correct language/current-version metadata through reviewed services, and keep invalid/demo facts excluded.
- Likely files: KG seed/repair script, `backend/app/services/knowledge_graph_production_scope_service.py` tests, KG acceptance report.
- Database migration: no schema migration expected; reviewed data repair only.
- Vector regeneration: no.
- Real provider required: no; deterministic/manual extraction is sufficient.
- Expected metric improvement: production-eligible grounded nodes/edges from 0 to a nonzero reviewed set; KG citation validity 100% for that set.
- Change risk: high if gates are weakened or unreviewed facts are auto-accepted.
- Regression tests: archived/wrong-language/wrong-version exclusion, source trace and duplicate relation identity.
- Acceptance criteria: at least one reviewed fault-to-cause-to-action chain per manufacturer passes the existing production gate and can be cited without admitting demo facts.
- Recommended sequence: 8.

## 9. T26J-VECTOR-LIFECYCLE - Reconcile Archive/Reparse State Incrementally

- Classification: `SHOULD_OPTIMIZE_BEFORE_DELIVERY`.
- Feature: Vector lifecycle and retrieval hygiene.
- Current evidence: document archive updates PostgreSQL document/chunk status, but no archive-time DashVector delete was found; current remote reconciliation was not executed.
- Current status: `IMPLEMENTED_UNVERIFIED`/`BLOCKED` for remote consistency.
- User-visible impact: stale vectors can increase latency/noise even though PostgreSQL validation should stop final archived citations.
- Competition score impact: medium for stability and explainability, lower than scope/query fixes.
- Root cause: PostgreSQL lifecycle is authoritative but remote vector deletion/reconciliation is not part of the same reviewed operation.
- Minimum change: add a dry-run reconciliation report and idempotent delete/upsert queue for archived/reparsed affected documents; validate metadata before any remote mutation.
- Likely files: `backend/app/services/vector_store_adapters/dashvector_adapter.py`, document lifecycle service, a bounded reconciliation script and tests.
- Database migration: no expected.
- Vector regeneration: incremental affected-document upsert/delete only; explicitly no full rebuild.
- Real provider required: yes for final remote verification, not for dry-run diff.
- Expected metric improvement: zero stale candidate IDs in the sampled scope and lower candidate noise/latency variance.
- Change risk: high because a bad filter could delete valid vectors.
- Regression tests: dry-run first, archived/reparsed/current versions, idempotency, failed remote call and PostgreSQL final validation.
- Acceptance criteria: dry-run count is reviewed; bounded apply leaves sampled PostgreSQL and DashVector IDs/metadata consistent without touching unrelated partitions.
- Recommended sequence: 9.

## 10. T26K-SOP-REGRESSION - Stabilize A Repeatable Dual-vendor Work Demo

- Classification: `SHOULD_OPTIMIZE_BEFORE_DELIVERY`.
- Feature: SOP and standardized maintenance work.
- Current evidence: eight active templates, 11 completed executions, eight completed tasks and one fully closed workflow with seven execution records exist; only one workflow has a complete step-level evidence chain.
- Current status: `VERIFIED`, L4.
- User-visible impact: the feature works, but a single complete chain is fragile for a live demonstration.
- Competition score impact: medium risk reduction rather than feature completion.
- Root cause: acceptance depth is concentrated in one workflow.
- Minimum change: create deterministic, reversible acceptance fixtures for one Huawei and one Sungrow scenario using existing APIs and policies; verify risk-level steps, evidence, completion request, acceptance and record-center trace.
- Likely files: a dedicated acceptance script and report; no core service rewrite unless a reproduced defect is found.
- Database migration: no.
- Vector regeneration: no.
- Real provider required: no; use approved knowledge/rule fallback and state the source.
- Expected metric improvement: two repeatable end-to-end work scenarios and 100% expected audit events.
- Change risk: low if isolated fixture prefixes and cleanup/dry-run controls are used.
- Regression tests: non-skippable safety step, invalid transition, expert gate, rejected completion, final record and cleanup.
- Acceptance criteria: both scenarios run from diagnosis/SOP selection to accepted completion with complete actor/time/evidence trace and no policy bypass.
- Recommended sequence: 10.

## Deferred Until After Competition

The following are `CAN_DEFER_AFTER_COMPETITION`:

- Replace or add a dedicated Qwen/LLM reranker before the fixed benchmark proves a deterministic ceiling.
- Change the embedding model or perform a full vector rebuild.
- Add raw-image embedding or image-to-image vector search.
- Expand the KG automatically from every document or correction.
- Add Neo4j; the current PostgreSQL graph model is adequate for the competition scope.
- Globally retune chunk size/overlap; first target table-heavy documents only.
- Optimize broad historical 150-case prompts that are outside the final competition benchmark.
- Stream very large uploads and clean pre-persistence orphan files, unless a delivery stress test reproduces the issue.

## Do Not Change Before Delivery

The following are `DO_NOT_CHANGE_BEFORE_DELIVERY`:

- FastAPI -> service -> repository -> SQLAlchemy architecture.
- PostgreSQL as the source of truth, `/api` public prefix and unified response shape.
- Human approval for documents, contributions, corrections, KG facts and high-risk maintenance work.
- Existing SOP non-skippable safety, evidence and completion-verification policies.
- Real-citation validation and archived/pending exclusion.
- Provider safety boundaries and explicit blocked/fallback states.
- Multiple core models/providers at once without a frozen baseline.
