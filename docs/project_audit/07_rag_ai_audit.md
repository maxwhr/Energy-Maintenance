# RAG And AI Capability Audit

## Executive Truth

The repository contains a substantial retrieval and AI integration architecture, not a fixed-answer placeholder. PostgreSQL keyword retrieval and source tracing are first-class paths. Embedding, DashVector, reranking, cloud/local model, OCR and multimodal adapters also exist. However, this audit did not invoke real external services, so their current operational state is `BLOCKED`. The default code path remains protected by keyword fallback and conservative answer boundaries.

## Capability Classification

| Capability | Classification | Evidence/limit |
|---|---|---|
| PostgreSQL knowledge documents/chunks | Exists and schema verified | `models/knowledge.py`; live metadata/table comparison. |
| TXT/MD/PDF/DOCX parsing | Exists, unverified this audit | `services/document_parser.py`; dependencies in pyproject. |
| Chunking | Exists, unverified this audit | `text_splitter.py:21-23,81-153`; default 1000/150. |
| Keyword retrieval | Exists, unverified write path | `retrieval_service.py:559-645`; query POST not called. |
| Real references from chunks | Exists, statically verified | `retrieval_service.py:226,682-702,806-840`. |
| QA record persistence | Exists, statically verified | PostgreSQL `qa_records`; transaction at `retrieval_service.py:806-840`. |
| Embedding service | Exists, current availability blocked | `embedding_service.py`; no real call. |
| DashVector adapter/index metadata | Exists, current availability blocked | `vector_index_service.py`, DashVector adapter/tables. |
| Hybrid fusion/feature reranking | Exists, blocked by current vector verification | `hybrid_retrieval_service.py:40-147`. |
| Dedicated model rerank/query understanding | Exists, no current real provider call | model adapters and query-understanding services. |
| Rule/fallback answer boundary | Exists | grounded answer and fallback services. |
| Cloud LLM | Configured path exists; blocked | no authorized current real call. |
| Local llama.cpp | Code exists; blocked | runtime flag disabled. |
| OCR | Code exists; blocked | runtime flag disabled; no recognition call. |
| Multimodal evidence | PostgreSQL/business path exists; real AI blocked | media/multimodal services and tables. |
| Knowledge graph augmentation | Partial | graph infrastructure exists; current Chinese production grounding insufficient. |

## Model And Provider Configuration

Configuration is environment-driven through `backend/app/core/config.py`:

- local model timeout/model/API type: lines 49-58;
- OCR provider/language/timeout: lines 60-65;
- cloud model timeout/max tokens/temperature: lines 77-88;
- DashVector collection, metric, batch and timeout: lines 193-221;
- hybrid weights/budgets/fallback thresholds: lines 224-235;
- embedding provider/model/dimension/batching/retry/cache: lines 237-258.

Secrets are not stored in the provider tables or included in this report. External call logs are designed to retain sanitized summaries. Current availability cannot be inferred only from enabled flags or historical reports.

## Embedding

Positive controls:

- Empty/invalid output is checked; vector count, dimension and finite numeric values are validated (`embedding_service.py:102-180`).
- Calls are batched and query embeddings have a bounded TTL/count cache.
- Cache keys hash normalized text and do not expose the query.
- Index versioning is represented in configuration/metadata.
- PostgreSQL does not store raw vectors in the audited design.

Unverified/risks:

- The current provider response dimension was not re-probed. Names indicate the intended 1024-dimensional `text-embedding-v4` route, while configuration defaults are zero until environment values resolve.
- Model switching/reindex safety depends on versioned index metadata and controlled scripts; no full reindex was permitted.
- Current real Embedding availability, latency, quota and retry behavior are blocked in this audit.

## Document Processing

- Supported formats: TXT, MD, PDF and DOCX.
- TXT/MD decode and PDF/DOCX parsing are implemented.
- Chunk default: 1000 characters, overlap 150; paragraph boundaries are preferred.
- Chunk content receives SHA-256 `content_hash` and source metadata.
- Parse failure clears chunks and records `failed/error_message`.
- Review status gates prevent unapproved knowledge from the production retrieval scope.

Gaps:

- No dedicated duplicate-file hash field was confirmed at the document level; chunk hashes help content identity but are not a complete upload deduplication contract.
- Table and image semantics from PDF/DOCX are limited to parser extraction; scanned PDFs require OCR, currently blocked.
- Upload buffering and orphan-file compensation risks are tracked as AUD-007/AUD-008.

## Vector Store

The selected external vector design is DashVector, not pgvector. PostgreSQL remains authoritative, and vector hits are rehydrated/validated against PostgreSQL before being surfaced.

Controls observed:

- cosine distance configuration;
- versioned logical/physical collection names;
- partition support;
- top-k and similarity thresholds;
- batched upserts;
- query timeout and keyword fallback;
- raw vector values are not returned in normal diagnostics;
- fake in-memory adapter is explicitly labeled test-only (`vector_index_service.py:535-669`).

No current remote count, consistency query, backup/restore or real index write was performed in this audit.

## Retrieval Flow

The actual flow is:

1. Normalize and understand the question.
2. Expand Chinese/domain terms.
3. Query PostgreSQL candidates with metadata/review filters.
4. Optionally query Embedding/DashVector in an isolated session with a 3.5-second vector budget.
5. Fuse keyword/vector scores, optionally rerank, refine and deduplicate.
6. Apply abstention thresholds and protect strong keyword evidence.
7. Build references from real document/chunk objects.
8. Build a bounded answer and persist the request/response trace.

Evidence: `retrieval_service.py:113-337,426-515,559-702,806-840`.

Top-k validation is bounded to 1-10 for surfaced results; vector candidate top-k is bounded to 1-50. Fallback diagnostics and external call counts are recorded.

## Generation And Hallucination Boundaries

`ModelPromptBuilder` explicitly prohibits invented references, manufacturer instructions and unsupported image interpretation (`model_prompt_builder.py:20-33,88-93,153-166`). Citation validation and grounded answer boundary services exist, and ambiguous/high-risk queries can suppress repair instructions.

Remaining design risk:

- No dedicated prompt-injection detector or trust-label parser was found. Retrieved/user text is structurally labeled in a prompt, but malicious instructions inside approved content still depend on model instruction hierarchy and output validation.
- Model output remains advisory and must be human-reviewed for maintenance decisions.
- Streaming output was not identified as a verified feature.
- Current token/cost/latency behavior of real providers was not revalidated.

## Evaluation

The repository includes extensive retrieval evaluation schemas, datasets, pilot/freeze/run services and historical quality reports. Current test collection includes related tests. This audit did not rerun the write-heavy benchmark suite or real providers.

Important current evidence:

- Historical/current reports identify quality gates separately from code availability.
- Task 25G R2 concludes current Chinese KG grounding is insufficient.
- Current smoke intentionally skipped retrieval write.
- Full pytest was unsafe due database isolation, so prior pass counts are historical snapshots, not this audit's result.

## Current Claims Allowed

- PostgreSQL-backed document/chunk schema and keyword/hybrid retrieval implementation exist.
- The code builds real references from stored chunks and persists QA traces.
- External vector/model paths are adapter-based, bounded and have fallback logic.
- DashVector is the designed vector backend; pgvector/Neo4j are not used.

## Claims Not Allowed From This Audit

- Real Embedding or DashVector is currently online and correct.
- Cloud/local model currently generates successful maintenance answers.
- OCR currently recognizes uploaded images.
- Hybrid retrieval currently outperforms keyword retrieval in production.
- Knowledge graph currently improves production answers.
- RAG quality is globally passed on the current configuration.

## Recommended Next Audit

After test-database isolation and Git baseline repair, run a controlled RAG audit with frozen Huawei/Sungrow cases, read/write row-count guards, explicit external-call authorization, provider configuration hashes, citation correctness, no-answer behavior, Chinese terminology, latency/cost and fallback failure injection.

