# Formal Knowledge Frontend and RAG Acceptance

## Scope and Safety Boundary

This R3C acceptance used a temporary FastAPI process on `127.0.0.1:8011`
against the formal PostgreSQL database started with
`default_transaction_read_only=on`. It did not perform an importer Apply,
upload, reparse, review transition, database migration, vector rebuild, or
external provider call.

The normal login endpoint updates `users.last_login_at`, so an intentional
read-only login probe was rejected by PostgreSQL. This is expected behavior and
left no change. The login form rendered in Chrome, then the browser received a
locally signed JWT for the existing administrator after a read-only lookup of
that user's ID. This allowed the actual frontend pages and API requests to be
tested without disabling database write protection. It is not represented as a
successful writable `POST /api/auth/login` acceptance in this report.

## Browser Evidence

- Chrome CDP loaded the real static frontend served by FastAPI.
- The knowledge document list showed all 10 R3B Huawei SUN2000 documents.
- A real document-list chunk button was clicked for document
  `27ed5237-9ace-4eba-8fa0-197447cea45a`.
- The returned chunk page contained 59 real persisted chunks with non-empty
  parsed content.
- The document detail exposed its formal import source-relative path.
- The query-aware knowledge-search page loaded successfully.
- The browser result recorded no console errors and no new 4xx/5xx API failures
  in the authenticated read-only session.

The frontend search form currently sends `persist_result=true`. R3C therefore
did not submit its form, because it would violate the formal database read-only
boundary. The ten retrieval requests were issued by same-origin browser
`fetch` from the loaded search page with `persist_result=false`,
`enable_llm=false`, and `allow_real_api=false`.

## Targeted RAG Results

| Result | Count |
| --- | ---: |
| Target documents tested | 10 |
| Documents with at least one own real citation | 9 |
| Target citations from Sungrow | 0 |
| Persisted QA records created | 0 |
| External provider calls caused by R3C | 0 |
| Vector rebuilds caused by R3C | 0 |

Nine documents returned citations to their own imported document ID using their
title query. The remaining document,
`b5424104-c986-482a-b297-9e251adbc7c9` (SUN2000 quick guide, Amphenol), did
not return an own citation after title, title-plus-section, and all nine parsed
chunk-excerpt queries. It remains a retrieval coverage blocker.

The generalized query for inverter alarm troubleshooting returned 10 real
citations, all from the imported inverter alarm reference document. This is an
observation only; R3C did not change ranking to force different results.

## Read-Only Post-Acceptance Reconciliation

`.runtime/task28a-r3c/post_browser_read_only_reconciliation.json` passed:

- `knowledge_documents=382` and `knowledge_chunks=5728` remained unchanged.
- All ten imported documents and their 937 chunks remained present and healthy.
- `qa_records=2598` remained unchanged.
- Protected non-knowledge counts remained unchanged.
- `external_api_call_logs=676` and `vector_index_runs=88` remained unchanged.

## Status

`PARTIAL_RAG_COVERAGE_BLOCKED`

The browser data-display and source-trace path pass. Formal import integrity
passes. The R3C condition requiring every one of the ten newly imported
documents to be reached by a targeted query-aware retrieval does not pass.
The next authorized task should diagnose the retrieval candidate/ranking path
for the approved Amphenol quick guide without re-importing, re-parsing, or
changing formal knowledge data.

## Task 28A-R3D Superseding Coverage Result

R3D completed the permitted citation-validation repair and repeated formal
read-only acceptance against port `55432`:

- The target PDF had already entered the candidate/rerank path; it was omitted
  because page-only chunks lacked a section title required by the old citation
  validator.
- The generic fix accepts a real parent document title as the traceable
  fallback only when an approved/active, in-scope, non-empty PDF chunk also has
  a real page locator. It does not alter data, scope, or candidate retrieval.
- All ten R3B Huawei documents now return at least one own real citation. The
  Amphenol quick guide passes title, model, and content queries (best own rank
  1); Sungrow citations remain zero.
- The real static search page rendered the target citation during a same-origin
  preview request (`persist_result=false`); document/chunk tracing passed with
  zero browser console errors and zero authenticated API 4xx/5xx responses.
- No QA records, provider-call logs, vector runs, documents, or chunks were
  added by R3D.

This supersedes the R3C 9/10 coverage result. It does **not** make the overall
formal RAG gate passed: the frozen 30-case engineering evaluation remains
`NOT_READY` with Recall@1 `0.392857`, Recall@3 `0.714286`, Recall@5
`0.821429`, MRR `0.560714`, nDCG@5 `0.626207`, and citation support
`0.821429`. The authoritative status is therefore
`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL`.
