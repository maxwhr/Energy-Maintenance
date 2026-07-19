# Competition Feature Status

Audit date: 2026-07-16

## Evidence Boundary

This is a read-only audit of the current working tree and PostgreSQL data. No business API that writes data was invoked, no provider call was made, and no vector index was changed. Historical reports are supporting context only. Status uses the Task 26A vocabulary.

## Status Matrix

| Feature | Subfeature | Status | Maturity | Frontend evidence | Backend evidence | Data evidence | Runtime evidence | Current issue | Delivery requirement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Text RAG | Upload and file safety | VERIFIED | L4 | `knowledge/Documents.vue` | `KnowledgeService.upload_and_process_document` | TXT/MD/PDF/DOCX rows exist | Previous real closed-loop evidence; current code inspected | Upload buffers the whole file and can leave a file before document persistence | Yes, with known limits |
| Text RAG | Parse and chunk persistence | VERIFIED | L4 | Chunk preview exists | `DocumentParser`, `SemanticChunker` | 0 parsed-zero, 0 failed-nonzero, 0 chunk-count mismatch | Read-only integrity query passed | Scanned PDF still requires OCR | Yes |
| Text RAG | Metadata and review | VERIFIED | L4 | Document review page | Review service and retrieval guards | Review history exists; approved/active filters present | Current DB inspected | Sungrow approved documents lack normalized-language and pilot metadata | No for dual-vendor delivery |
| Text RAG | Huawei production corpus | VERIFIED | L4 | Search and QA pages | Keyword and scoped retrieval | 63 default-eligible Huawei docs, 1,393 chunks | Current DB inspected | Pilot scope also includes LUNA2000/SmartLogger | Partial |
| Text RAG | Sungrow production corpus | BROKEN | L2 | Sungrow is selectable in legacy QA | Default language filter and fixed pilot scope | 15 approved active docs/102 chunks, but 0 default-eligible and 0 pilot-scope docs | Current scope resolution inspected | Neither public default path nor query-aware pilot path includes Sungrow evidence | No |
| Text RAG | Deterministic query understanding | PARTIAL | L2 | Query-aware search UI | Signal extraction and old query understanding services | Evaluation cases exist | Pure deterministic probes run | Query-aware extractor misses `SG110CX`, numeric-only `2061`, manufacturer aliases and common typo `通迅` | No |
| Text RAG | Keyword retrieval | PARTIAL | L3 | Legacy QA page | PostgreSQL `ILIKE`, status filters and weighted rank expression | Approved chunks exist | Code and DB inspected | Broad `ILIKE` OR scan; default filter excludes all Sungrow; exact model is not an SQL filter | No |
| Text RAG | Embedding and DashVector | BLOCKED | L3 | Retrieval quality page | Embedding, lifecycle and DashVector adapters exist | Vector index metadata and historical runs exist | Configuration completeness checked without a provider call | Current latency, dimension and remote reconciliation were not reverified | No current claim |
| Text RAG | Hybrid fusion and rerank | PARTIAL | L3 | Mode controls and diagnostics | Multi-query, RRF, deterministic rerank and dedicated rerank fallback exist | Four evaluation runs exist | Current flags: deterministic on, dedicated rerank off | Results are unstable across datasets; no current real reranker run | No |
| Text RAG | Answer and citations | PARTIAL | L3 | Legacy QA shows answer/references; query-aware page shows evidence boundary | Rule-based answer, citation validation and abstention exist | 2,597 QA rows | Code/DB inspected, no write call made | Query-aware primary page does not generate a user-oriented answer or save a QA record | No |
| Text RAG | Quality evaluation | PARTIAL | L3 | Retrieval quality page | Evaluation services and frozen-set controls | 2,540 cases, 4 runs, one 30-case freeze; only one expert-verified case | Metrics read from DB | Controlled 30-case result is strong, broad 150-case result is poor; benchmark representativeness is unresolved | No |
| Multimodal | Upload and validation | VERIFIED | L4 | Multimodal maintenance page | Media validation/storage services | 414 media rows | Current code/DB inspected | No current live upload executed in this read-only audit | Yes |
| Multimodal | OCR and vision adapters | BLOCKED | L3 | Evidence center/provider status UI | OCR/MIMO gateway and real/mock boundaries exist | Historical: 18 real OCR and 13 real MIMO analyses; current provider rows are blocked | No provider call made | Current real availability is not verified | No |
| Multimodal | Structured evidence and human correction | VERIFIED | L4 | Confirm/reject/clarify controls | Case orchestrator, evidence fusion/conflict services | 156 evidence items, 14 open conflicts, user-confirmed evidence exists | Current DB inspected | All 14 conflicts remain open | Partial |
| Multimodal | Cross-modal retrieval and diagnosis | PARTIAL | L3 | Cross-modal workflow page | OCR/vision evidence -> query plan -> scoped retrieval -> diagnosis code exists | 27 cases, 25 hypotheses; persisted draft states exist | Code/DB inspected | Frontend requests `allow_real_api: false`; retrieval inherits Huawei-only pilot scope | No |
| SOP/work | SOP recommendation and safety | VERIFIED | L4 | SOP center | Template/rule engine, knowledge references and safety requirements | 8 active templates (5 Huawei, 3 Sungrow) | Current code/DB inspected | Rule templates dominate when grounded KG is empty | Yes |
| SOP/work | Task execution and verification | VERIFIED | L4 | Maintenance workflow and work-order pages | Non-skippable safety steps, evidence and completion verification policies | 11 completed SOP executions, 8 completed tasks, one fully closed workflow with seven execution records | Persisted closed loop inspected | Only one workflow has full step-level evidence | Yes for demo, should broaden |
| Knowledge | Contribution and expert review | VERIFIED | L4 | Contribution page | Draft/submit/reject/resubmit/approve/archive services | 126 contributions and 174 review records | Current DB inspected | Large draft/pending backlog | Yes |
| Knowledge | Convert approved contribution | VERIFIED | L4 | Convert action and converted-document display | Transactional document/chunk conversion | 8 converted contributions linked to 8 documents | Current DB inspected | No automatic graph extraction is required or desired | Yes |
| Knowledge | Knowledge graph CRUD/display | VERIFIED | L3 | Graph page | PostgreSQL KG services and review controls | 34 active nodes, 34 active edges | Current DB inspected | Most facts are final-demo seed data | Partial |
| Knowledge | Production-grounded KG use | BROKEN | L2 | Retrieval/diagnosis/SOP can display KG context | Production scope correctly rejects invalid evidence | 0/34 eligible nodes, 0/34 eligible edges, 0 grounded evidence; all 76 links excluded | Current production-scope service executed read-only | Evidence documents are `language_en`; some are archived | No |
| Correction | Submit and preserve original output | VERIFIED | L3 | Correction form/detail | Source validation and immutable original/corrected payloads | 15 corrections; source trace, submitter and reviewer retained | Current DB inspected | No quick helpful/unhelpful feedback taxonomy | Partial |
| Correction | Expert accept/reject/history | VERIFIED | L3 | Review actions | Role-gated resolve service | 8 accepted, 5 archived, 1 pending | Current DB inspected | Accepted corrections are not versioned as formal knowledge | Partial |
| Correction | Feed approved correction back to knowledge | NOT_FOUND | L0 | No conversion action | No correction-to-contribution service path | `converted_contribution_id` is null for all 15 corrections | Current code/DB search | Later retrieval cannot use an accepted correction | No |

## Feature Summaries

### A. Text RAG And Knowledge Retrieval

- Current completion: `PARTIAL`, maturity `L3`.
- Strongest part: file processing, PostgreSQL chunk integrity, review filtering, source validation and extensive evaluation instrumentation.
- Weakest part: the live competition scope is not dual-vendor; query-aware deterministic entity extraction misses Sungrow models and numeric-only alarm codes.
- Demo: Huawei controlled-corpus evidence retrieval can be demonstrated. Sungrow cannot be represented as production-ready.
- Delivery: not ready.
- Minimum completion: repair scope/metadata/entity extraction, persist query-aware QA traces, then pass a representative dual-vendor frozen set.

### B. Multimodal Fault Image Retrieval

- Current completion: `PARTIAL`, maturity `L3`.
- Strongest part: media persistence, evidence/conflict model, user confirmation, cross-modal orchestration and safety boundaries.
- Weakest part: current real OCR/vision provider status is blocked and the UI defaults to no real call.
- Demo: existing persisted cases can be demonstrated; a new-image live recognition claim is unsafe.
- Delivery: not ready as a live multimodal capability.
- Minimum completion: current provider health check plus four-image controlled acceptance and cross-modal dual-vendor retrieval.

### C. Standardized SOP And Maintenance Work

- Current completion: `VERIFIED`, maturity `L4`.
- Strongest part: explicit human gates, non-skippable safety steps, evidence records and completion verification.
- Weakest part: only one current workflow contains a complete step-level evidence chain.
- Demo: yes.
- Delivery: yes, with a curated repeatable demo workflow.
- Minimum completion: no architectural change; add regression coverage and stable demo data only.

### D. Knowledge Contribution, Review And Knowledge Graph

- Current completion: `PARTIAL`, maturity `L3`.
- Strongest part: contribution review and conversion to a real approved document/chunks.
- Weakest part: production-grounded graph context is empty; most active graph facts are demo seed data.
- Demo: contribution lifecycle and graph page are demonstrable, but production KG enhancement is not.
- Delivery: contribution workflow yes; combined contribution-to-grounded-KG capability no.
- Minimum completion: repair evidence language/current-version grounding and approve graph candidates without bypassing human review.

### E. Model Answer Annotation And Manual Correction

- Current completion: `PARTIAL`, maturity `L2`.
- Strongest part: trace-linked original/corrected output, submitter, reviewer and review history are persisted.
- Weakest part: accepted corrections have no route into a contribution, document, chunk or later retrieval.
- Demo: submission and review can be shown.
- Delivery: no, because the learning/knowledge-update loop is open.
- Minimum completion: accepted correction -> draft contribution -> existing human review -> approved document/chunks, with regression proof that later retrieval can cite it.
