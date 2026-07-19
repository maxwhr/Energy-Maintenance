# Task 25G-R1 Knowledge Graph Grounding Remediation Report

## 1. Final Status

- Final result: `TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT`.
- Task 25G original status: `TASK25G_KG_GROUNDING_GATE_FAILED`.
- Forensics: PASS; all 12 reported evidence rows were traced to one archived English maintenance-record document and two distinct graph facts.
- Classification audit: PASS; pending and marketing leakage were false-positive labels, while archived and English leakage were real.
- Grounding remediation: scope enforcement and governance candidates applied; no evidence was rebound because no exact current successor exists.
- KG integration: PASS with safe empty-context degradation.
- KG performance: PASS.
- Static LoongArch/Kylin preparation remains as frozen by Task 25G; real-machine acceptance was not executed.
- Full extraction, full reindex, embedding, and vector production writes were not executed.

The graph is not production-ready for retrieval or diagnosis because it has zero facts backed by current, active, Chinese, engineering-approved evidence. This report does not convert an empty production context into a pass.

## 2. Leakage Baseline and Forensics

| Item | Original Task 25G | Verified R1 |
|---|---:|---:|
| leaked evidence | 12 | 12 historical rows investigated |
| archived leakage | not independently reported | 12 |
| pending leakage | 12 | 0 |
| marketing leakage | 12 | 0 |
| approval leakage | combined with invalid scope | 0 |
| English leakage | not detected by the old static audit | 12 |
| superseded leakage | not independently reported | 0 |

The old audit used a combined invalid-document-state signal and assigned the same 12 archived rows to both pending and marketing categories. R1 now evaluates lifecycle, review, category, language, parse status, supersession and locator validity independently. Result: 12 evidence rows had two false labels each, for 24 false-positive label assignments. `maintenance_record` is a source category; it is not equivalent to pending or marketing.

Forensic exports contain identifiers, hashes and locators required for engineering review. The Markdown report intentionally excludes complete document titles and source text.

## 3. Document Version and Evidence Equivalence

- Archived documents investigated: 1.
- Explicit current successor found: 0.
- Exact successor support: 0.
- Partial successor support: 0.
- No explicit current successor: 1.
- Historical maintenance-record evidence rows: 12.
- Equivalence result: `{"NOT_FOUND": 12}`.
- Automatic rebind allowed/executed: 0.
- LLM equivalence judgment: false.

Title similarity was not used for automatic binding. Product family, model, relation, subject/object, alarm/component signals, semantic source and current source locator would all have been required for `EXACT_SUPPORT`.

## 4. Evidence Remediation

- Exact support: 0.
- Rebound evidence: 0.
- Reused current evidence: 0.
- Historical evidence preserved: 12.
- Historical evidence excluded from production context: 12.
- Unsupported-current facts in the original leakage set: 2.
- Active graph facts without current valid Chinese evidence globally: 68.
- Remediation candidates: 2 pending manual governance candidates.
- OperationLog coverage: 14 operations.
- Automatic fact deletion: 0.
- Evidence deletion: 0.
- Candidate auto-approval: 0.
- Expert auto-write: false.

The remediation plan contained 12 source-derived production-scope exclusions and two candidate creations. The explicit apply was transactional and idempotent: the second apply reused both candidates and produced no duplicate candidate or OperationLog writes. Existing graph facts and evidence rows were not rewritten.

## 5. Production KG Scope

| Gate | Result |
|---|---:|
| production fact count | 0 |
| current-valid coverage over returned production facts | 1.00 (vacuous: zero returned facts) |
| current-valid coverage over all active graph facts | 0.00 |
| archived evidence in production context | 0 |
| pending leakage | 0 |
| marketing leakage | 0 |
| approval leakage | 0 |
| English leakage | 0 |
| superseded leakage | 0 |
| scope leakage | 0 |
| unsupported facts returned | 0 |

Production APIs now require an active fact with at least one current, active, parsed, Chinese, engineering-approved, non-marketing, non-pending, non-superseded and non-archived source plus a valid active chunk locator. Admin/audit views can still inspect historical evidence. The zero leakage result is caused by exclusion at the source boundary, not by deleting history or disabling the graph module.

## 6. KG Integration Truth Audit

- Citation preservation: 1.00; vacuous for the current empty production context, but every future returned fact must carry evidence IDs.
- Source locator coverage: 1.00; vacuous for zero returned facts and enforced by source validation.
- Unsupported graph facts returned: 0.
- Archived baseline evidence returned: 0.
- Diagnosis grounding boundary: PASS; the diagnosis path uses the same production-scoped business context and cannot consume unsupported historical facts.
- Workflow automatic graph writes: 0.
- Correction boundary: PASS; completion creates review candidates only and does not mutate the formal graph.
- Knowledge Curator explicit review: PASS.
- Safe degradation when graph context is empty: `PASS`.

## 7. Alias and Orphan Review

- Orphan active node count: 1.
- Orphan classification: `HISTORICAL_ONLY`; it was not deleted and is not returned in production context.
- Alias collision count: 2.
- `SAFE_EQUIVALENT`: 0.
- `CONTEXT_DEPENDENT`: 0.
- `INCOMPATIBLE`: 2.
- `UNRESOLVED`: 0.
- Unsafe automatic resolution: 0.
- Deterministic canonicalization policy: true.

Both collisions are incompatible and require clarification/context; no node merge or default canonicalization was performed.

## 8. Performance Preservation

| Operation | R1 p95 | Hard gate | Result |
|---|---:|---:|---|
| node search | 1.275 ms | 500 ms | PASS |
| alias resolution | 0.822 ms | 300 ms | PASS |
| one-hop expansion | 0.674 ms | 800 ms | PASS |
| two-hop expansion | 0.657 ms | 1500 ms | PASS |
| RAG KG context | 39.692 ms | 1200 ms | PASS |

- Maximum SQL count: 4 (gate: <=25).
- Serializer SQL: 0.
- N+1 detected: false.
- Performance regression failures: 0.

## 9. Regression and Reconciliation

| Group | Result |
|---|---|
| compileall | PASS |
| Alembic heads/current | PASS (`20260712_0015`) |
| pytest | PASS (470 passed, 3 skipped) |
| security | PASS |
| RBAC | PASS |
| RAG | PASS |
| agents | PASS |
| Knowledge Curator | PASS |
| Task 25D | PASS isolated live replay |
| Task 25E | PASS current live-baseline core replay |
| Task 25F-R1 | PASS |
| Task 25G original report/runtime frozen | PASS |
| Task 25G core regression | PASS |
| final smoke | PASS |

Task 25E's original response hash remains a historical database snapshot and was not relabeled. R1 generated an isolated current baseline and passed SQL trace, response parity, performance, concurrency, large-dataset, write-visibility and RBAC checks. Volatile Task 25D/25E browser JSON was re-generated during verification; browser semantics passed, while the R1 report relies on Task 25G's own frozen report/runtime hash reconciliation.

Existing regression scripts temporarily created exact Task24B/Task24D test fixtures. The existing scoped cleanup removed only post-snapshot marked fixtures; formal documents deleted=0. Final reconciliation confirms vector namespaces and counts match the R1 snapshot.

## 10. Integrity and Boundaries

- PostgreSQL-only graph persistence: yes.
- Neo4j: not used.
- pgvector: not introduced by this task.
- New migration: none.
- Alembic current/head: `20260712_0015`.
- Task 25G original report unchanged: true.
- Task 25G original runtime unchanged: true.
- `backend/.env` unchanged: true.
- ZIP inventory unchanged: true.
- pilot_r2 / pilot_r3_semantic / pilot_r4_grounded / pilot_r5_query_aware: unchanged.
- Net vector namespace change: false.
- Remediation vector writes: 0.
- Remediation embedding writes: 0.
- Full reindex: false.
- Knowledge document/chunk content updates: 0.
- Approval state changes by remediation: 0.
- `expert_verified=true` writes: 0.
- Task 25C remains `MULTIMODAL_BENCHMARK_INSUFFICIENT`.
- R6 remains `DEFERRED_QWEN3_RERANK_CONFIG`.
- Package/ZIP generated: no.
- Git add/commit/reset/clean/restore: not executed.

## 11. Deployment Boundary

Task 25G's static LoongArch/Kylin portability, dependency and deployment-template checks remain frozen and unchanged. No LoongArch or Kylin real-machine test was executed in R1, so this report makes no real-machine acceptance claim.

## 12. Final Judgment

- KG production ready: **no**.
- KG deployment ready: **no for production use**, because no current valid Chinese engineering evidence backs any active graph fact.
- Static deployment preparation: retained from Task 25G.
- Real-machine acceptance required: yes.
- Remaining blocker: import or explicitly govern current, active, Chinese, engineering-approved source documents and establish exact evidence links through human review. Do not reactivate archived maintenance records or auto-approve candidates to clear this blocker.
