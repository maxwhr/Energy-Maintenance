# RAG Quality Evaluation

Audit date: 2026-07-16

## Evidence Boundary

This report is based on the current source tree, read-only PostgreSQL queries, deterministic pure-function probes, and previously persisted evaluation results. The audit did not write evaluation data, call a paid provider, mutate DashVector, or run an unisolated full test suite. Metrics that were not measured in this audit remain `BLOCKED` rather than being inferred from historical runs.

## 1. Current RAG Architecture

The repository contains two public retrieval paths:

1. Legacy QA: `/api/retrieval/query` -> query normalization -> PostgreSQL keyword candidate retrieval -> rule-based answer assembly -> citation validation -> `qa_records` persistence.
2. Query-aware search: `/api/retrieval/query-aware-search` -> signal extraction -> query variants -> fixed pilot scope -> keyword/vector candidates -> fusion/RRF -> deterministic rerank -> evidence boundary and citations.

Supporting components include PostgreSQL metadata filters, embedding adapters, a DashVector adapter, query expansion, deterministic and optional dedicated rerank, no-answer policies, citation validation, evaluation datasets, run/result persistence, and trace records.

## 2. Actually Enabled Path

| Item | Current state | Audit conclusion |
| --- | --- | --- |
| Default retrieval mode | `keyword` | The legacy QA path remains primarily PostgreSQL keyword retrieval. |
| Deterministic rerank | Enabled | Available on the query-aware path. |
| Dedicated reranker | Disabled/incompletely configured | `BLOCKED`; no current real reranker result may be claimed. |
| MiniMax ambiguity resolver | Disabled | Deterministic extraction remains authoritative. |
| Query-aware scope | Fixed Chinese engineering pilot scope | Contains 16 Huawei documents/1,262 chunks and no Sungrow document. |
| Active pilot session | None | Legacy QA uses the default-language gate rather than a session scope. |
| Query-aware QA persistence | Not implemented | It returns evidence-oriented output but does not create a `qa_records` row. |

The frontend search page uses the query-aware endpoint and displays the fixed 16-document/1,262-chunk scope. This path is useful for controlled Huawei evidence search, but it is not the required Huawei-and-Sungrow production QA path.

## 3. Current Provider Status

Only sanitized completeness flags were inspected. No URL, key, token, or secret was copied into this report.

| Provider/capability | Configuration evidence | Database status evidence | Current claim |
| --- | --- | --- | --- |
| PostgreSQL keyword retrieval | Present and read successfully | Current corpus queried | `VERIFIED` |
| Embedding configuration | Complete by boolean check | Historical vector metadata exists | `BLOCKED` for a current online result |
| DashVector | Adapter and metadata exist | Historical runs exist | `BLOCKED` for current dimension/latency/reconciliation acceptance |
| Dedicated reranker | Incomplete/disabled | No current accepted run | `BLOCKED` |
| Cloud text model | Config completeness present | Provider row reports `blocked` | `BLOCKED` |
| Local llama.cpp | Disabled/not configured | Provider row reports `not_configured` | `BLOCKED` |

## 4. Document And Chunk Quality

### Corpus eligibility

| Manufacturer | Approved active documents | Chunks | Default-eligible documents | Default-eligible chunks | Query-aware pilot documents |
| --- | ---: | ---: | ---: | ---: | ---: |
| Huawei | 72 | 1,404 | 63 | 1,393 | 16 |
| Sungrow | 15 | 102 | 0 | 0 | 0 |

All Sungrow documents fail the legacy default-language metadata gate, and none belongs to the fixed query-aware scope. This is a production-scope failure, not merely a low ranking score.

### Integrity checks

- Parsed documents with zero chunks: `0`.
- Failed documents with nonzero chunks: `0`.
- Stored `chunk_count` mismatches: `0`.
- Supported upload/parse extensions: TXT, MD, PDF, DOCX.
- Scanned-image PDF extraction remains OCR-dependent and is not a text parser guarantee.

### Sample audit

The task requested ten chunks per document. The two available Sungrow controlled documents each contain only eight chunks; all eight were inspected and the shortfall is itself evidence of corpus weakness.

| Sample | Status/scope | Sampled | Length evidence | Semantic observations | Retrieval risk |
| --- | --- | ---: | --- | --- | --- |
| Huawei manual `EDOC1100270192` | Approved/current | 10 of 95 | Median 412, average 474, range 127-1,336 | Models/codes and section/page context are generally retained; some chunks combine long lists/tables | Moderate: oversized mixed chunks may dilute scoring |
| Sungrow controlled manual `Task25BR1_Controlled_Document_09` | Approved but not production-eligible | 8 of 8 | Median 121, average 126 | Coherent but very small synthetic evaluation corpus, including hard negatives | High: not representative of a real manual and excluded by scope |
| Sungrow controlled fault case `Task25BR1_Controlled_Document_08` | Approved but not production-eligible | 8 of 8 | Median 120, average 125 | Coherent short cases, but narrow and synthetic | High: insufficient breadth and excluded by scope |
| Huawei SmartLogger alarm reference | `pending_review`, out of first-version product scope | 10 of 150 | Median 119.5, average 206, range 20-698 | Some header-only and repeated table-label chunks; pages absent | Moderate for chunking, but correctly blocked from retrieval |

The default chunk size/overlap are defensible for prose manuals, but table-heavy alarm references need structure-aware splitting. A global chunk-size change is not justified before a representative benchmark exists.

## 5. Query Understanding Quality

Deterministic probes were run without an external provider.

| Query pattern | Legacy understanding | Query-aware signal extraction | Result |
| --- | --- | --- | --- |
| `SUN2000` | Model recognized | Model recognized | Acceptable |
| `SG110CX` | Model recognized | Not recognized by current model regex | Failure on the primary search path |
| `2061` | Numeric alarm recognized | Numeric-only alarm not recognized | Failure on the primary search path |
| `绝缘阻抗低` | Domain expansion present | Partial structured extraction | Usable but path-dependent |
| `过温` | Domain expansion present | Partial structured extraction | Usable but manufacturer scope still matters |
| `MPPT 功率低` | Weak | Weak | Needs domain phrase mapping |
| `通迅不上` | Weak | Typo not normalized | Needs bounded typo normalization |
| Manufacturer aliases | Partially represented outside signals | No first-class manufacturer signal | Filter contamination risk |

The query-aware extractor recognizes `SUN2000`, `LUNA2000`, and `SmartLogger`, but not the required Sungrow SG family. Manufacturer, model, and fault code therefore do not consistently participate in filtering and exact-match protection.

## 6. Keyword Retrieval Quality

Strengths:

- Enforces approved/active document and chunk status.
- Uses title, section, content, document metadata and domain-weighted terms.
- Returns real document/chunk identifiers rather than fabricated references.
- Legacy path can persist the QA result.

Weaknesses:

- Broad `ILIKE` OR predicates can become expensive and imprecise.
- The default-language filter excludes every current Sungrow document.
- Exact SG model and numeric fault code are not consistently elevated on the query-aware path.
- Manufacturer constraints are not represented as a first-class extracted signal.

Current status: `PARTIAL`, L3.

## 7. Vector Retrieval Quality

Embedding, DashVector, index lifecycle and metadata contracts are implemented. Historical vector evaluation data exists. This audit did not perform an authorized current provider call or remote mutation; therefore current vector dimensions, collection state, latency, recall and PostgreSQL-to-DashVector reconciliation are `BLOCKED`.

The audit also found no archive-time DashVector deletion in the PostgreSQL document archive flow. PostgreSQL validation should prevent archived evidence from appearing in final results, but stale remote vectors can add cost and candidate noise until lifecycle reconciliation is implemented.

## 8. Hybrid Fusion And Rerank Quality

The source tree implements query variants, keyword and vector candidate pools, deduplication, RRF-style fusion, deterministic rerank, exact-signal protection, and fallback behavior. This is not a placeholder architecture.

However, quality is dataset-sensitive:

- A current stored 30-case controlled run is strong on generic recall/citation metrics but fails the overall gate because exact-model accuracy is zero.
- A broader stored 150-case run is poor and slow.
- Historical Task 25B R5 improved candidate recall but remained below final top-k quality thresholds.
- Dedicated reranking is disabled and a previous Qwen attempt did not establish a quality gain.

The evidence does not support changing embedding, reranker, and generation models together. Scope and deterministic signal errors must be fixed first.

## 9. Answer Quality

The legacy QA path produces a rule-based maintenance answer, suggested steps, safety content, confidence below 1.0, trace ID, real references and a `qa_records` row. It is functional but depends on the restricted legacy candidate corpus.

The query-aware path produces an evidence boundary, citations and diagnostic retrieval details, but no user-oriented final answer and no QA record. Since the frontend primary search experience uses this endpoint, the competition-facing answer loop is incomplete.

## 10. Citation Quality

Citation construction and validation use real PostgreSQL documents/chunks. Stored controlled runs report citation validity up to 1.0, while the broader run reports 0.833333. These are historical/current-database stored metrics, not a new Task 26A execution.

The principal citation risk is not fabricated IDs; it is citing a valid but wrong-scope or weakly supporting chunk after poor candidate selection. Archived PostgreSQL entities are guarded, while remote vector lifecycle cleanup remains incomplete.

## 11. Abstention And Safety Quality

- No-result responses can return empty references and reduced confidence.
- Electrical safety notes and human confirmation boundaries exist in QA, diagnosis and workflow layers.
- Historical R5 no-answer F1 was 0.833, but no representative current dual-vendor abstention run was executed.
- Cross-manufacturer mixing remains possible when manufacturer extraction/filtering fails.

Current status: implemented safeguards, `IMPLEMENTED_UNVERIFIED` for a current representative benchmark.

## 12. Evaluation Set

The database contains 2,540 evaluation cases, four runs and one frozen 30-case dataset. Only one case is marked expert-verified. The frozen set is engineering-controlled, not expert-verified, and does not establish representative Huawei-and-Sungrow coverage.

The broad dataset also includes historical/generic prompts and artificial page-instruction wording. It is useful for finding regressions but cannot be the sole competition acceptance set.

A delivery benchmark still needs at least:

- 12 Huawei questions covering insulation, communication, temperature, grid, DC, codes, models and safety.
- 12 Sungrow questions covering temperature, MPPT, communication, insulation, grid, codes, models and safety.
- 6 boundary questions covering missing knowledge, ambiguous manufacturer, wrong model/code, unsafe live work and off-domain input.
- Expected manufacturer/model/document/evidence, answer points, prohibited content, abstention and safety labels.
- Expert review and a frozen version identifier.

No new evaluation cases were written during this read-only audit.

## 13. Metric Results

### Task 26A current execution

All online/current RAG metrics are `BLOCKED` because a real provider/vector call or database-writing evaluation run was not authorized. The machine-readable report therefore records them as `null`.

### Stored results inspected read-only

| Stored run | Scope | Recall@5 | MRR | nDCG@5 | Citation | P95 | Gate |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| Latest controlled 30-case run | Engineering-controlled | 0.966667 | 0.95 | 0.954364 | 1.0 | 1,309.551 ms (hybrid) | Failed: exact-model accuracy 0 |
| Broad 150-case run | Historical/broad | 0.266667 | 0.189849 | 0.227692 | 0.833333 | 8,372.81 ms | Failed |
| Historical Task 25B R5 | Controlled blind set | R@5 0.70 | 0.64375 | 0.658087 | Validity 0.90 | Deep modes over budget | Failed |

These incompatible outcomes show benchmark and scope instability. They do not support a single claim that RAG is either universally good or universally bad.

## 14. Failure Cases

| Query | Expected | Actual | Returned documents | Returned chunks | Final answer | Failure type | Most likely root cause | Fix layer |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `SG110CX 温度太高` | Manufacturer Sungrow, model SG110CX, over-temperature evidence | Query-aware extractor does not emit SG model/manufacturer; production scope contains no Sungrow | Not executed in Task 26A; scope count proves zero eligible Sungrow documents | Not executed | Not generated | Scope + entity extraction | Fixed Huawei pilot and SG-absent model regex | Scope metadata and query signals |
| `华为 2061 告警` | Numeric code 2061 protected as exact alarm signal | Query-aware extractor does not recognize numeric-only code | Not executed | Not executed | Not generated | Fault-code understanding | Code regex requires an alphabetic prefix | Query signal extraction |
| `逆变器通迅不上` | Normalize typo to communication interruption and retrieve communication procedure | Typo remains unnormalized and domain intent is weak | Not executed | Not executed | Not generated | Query normalization | No bounded typo map for common maintenance wording | Query normalization/expansion |
| Stored broad-set PDF section prompt | Expected Huawei `EDOC1100167259` evidence | Top results repeatedly came from `EDOC1100273863` and other documents | Wrong Huawei document family | Stored run contains wrong-document top chunks; exact IDs were not re-emitted by this audit | Stored result failed expected evidence | Ranking/benchmark mismatch | Artificial page wording plus weak document discrimination | Benchmark curation, then title/model weighting |
| Sungrow generic maintenance question on legacy QA | Retrieve approved Sungrow manual/case evidence | All 15 approved Sungrow documents fail the default-language predicate | None eligible | None eligible | Low-confidence/no-source behavior expected | Metadata eligibility | Missing `normalized_language` and `is_default_retrieval_language` metadata | Metadata remediation |

## 15. Root Cause Classification

Priority order based on current evidence:

1. **Retrieval scope and metadata:** strongest root cause. Both public paths exclude Sungrow for different reasons.
2. **Query understanding:** SG models, numeric fault codes, manufacturer aliases and typos are not consistently structured.
3. **Evaluation representativeness:** strong controlled metrics conflict with poor broad metrics; only one case is expert-verified.
4. **Answer orchestration:** the primary query-aware UI does not produce/persist the full QA contract.
5. **Knowledge sufficiency:** Sungrow production material is sparse and dominated by tiny controlled documents.
6. **Chunk quality:** table-heavy references have header-only/oversized chunks, but this is not the first blocker.
7. **Vector/rerank:** not currently verified; no evidence that model replacement should precede the deterministic fixes.
8. **Prompt/generation:** not the primary cause because failures occur before answer generation.

## 16. Is Optimization Necessary?

Yes, but the RAG system does not need a broad rewrite. The architecture is substantial and several layers are sound. Delivery requires targeted repair of dual-vendor scope, deterministic query signals, query-aware answer persistence, benchmark quality and Sungrow corpus coverage.

## 17. Recommended Minimum Optimization

1. Create one current production retrieval scope containing only approved, active Huawei SUN2000/FusionSolar and Sungrow SG evidence; remove LUNA2000/SmartLogger from the competition default.
2. Backfill and validate Sungrow language/default-retrieval metadata without changing API contracts.
3. Extend deterministic signal extraction for Huawei/Sungrow aliases, SG model patterns, numeric alarm codes, MPPT/communication terms and a bounded typo map.
4. Make query-aware search return the user QA structure and persist traceable `qa_records`, reusing existing answer/citation services.
5. Freeze and expert-review a representative 30-case dual-vendor benchmark, then change one retrieval variable at a time.
6. Add real approved Sungrow manual/alarm/fault-case evidence to satisfy benchmark gaps; do not add arbitrary document volume.

## 18. Components Not Recommended For Change

- Do not replace PostgreSQL, FastAPI, Vue, or the `/api` contract.
- Do not globally change chunk size before table/manual subsets are benchmarked separately.
- Do not replace embedding, reranker and answer model simultaneously.
- Do not rebuild all vectors before scope/metadata and lifecycle discrepancies are known.
- Do not bypass document, contribution, correction or graph human review to inflate counts.
- Do not weaken archive/status/citation validation gates.
- Do not rewrite the working SOP safety/workflow architecture.
