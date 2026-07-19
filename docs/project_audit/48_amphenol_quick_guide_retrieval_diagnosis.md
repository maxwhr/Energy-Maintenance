# Task 28A-R3D: Amphenol Quick Guide Retrieval Diagnosis

## Boundary

This diagnosis ran only against the formal `energy_maintenance` database on
`127.0.0.1:55432` with PostgreSQL read-only protection enabled. Every retrieval
request used `persist_result=false`, `enable_llm=false`, and
`allow_real_api=false`. It did not import, reparse, review, update, archive, or
delete formal knowledge data; it did not use a vector index or an external
provider.

## Target Integrity

The approved target document remains healthy:

- ID: `b5424104-c986-482a-b297-9e251adbc7c9`
- title: `SUN2000-(20KTL-M3, 33KTL-NH, 40KTL-NH) 快速指南-(Amphenol)`
- scope: `huawei_sun2000_competition_v1`
- state: `parsed`, `approved`, `active`, `huawei`, `SUN2000`, `pv_inverter`
- chunks: nine non-empty, active chunks with contiguous indexes `0..8`
- review records: one or more
- source hash: present

The source snapshot is recorded in
`.runtime/task28a-r3d/baseline/pre_fix_baseline.json`. Diagnostics retain only
chunk IDs, hashes, page/locator metadata, and bounded previews.

## Root Cause and Loss Stage

The target chunk candidates were present in the approved Huawei scope, entered
the keyword candidate set, survived fusion and deterministic reranking, and
were real active chunks. The loss occurred at **citation validation / final
answer assembly**.

The quick-guide PDF has page locators but no recoverable section heading for
its chunks. The former PDF rule accepted only `page + section`, so valid target
chunks were rejected with `missing_pdf_page_or_section_locator`. This was not a
title-token, model-token, scope, manufacturer, review-status, or candidate
recall failure.

The read-only simulation of the former rule shows the exact effect:

| Query class | Raw candidate rank | Post-rerank/refinement rank | Own citation before fix | Loss stage |
| --- | ---: | ---: | --- | --- |
| Full title | 1 | 4 | none | citation or answer assembly |
| `20KTL-M3` model query | 1 | 4 | none | citation or answer assembly |
| Amphenol connector chunk query | 1 | excluded by refinement | none | presentation refinement after invalid citation removal |

Evidence: `.runtime/task28a-r3d/diagnostics/amphenol_pre_fix_simulated.json`.

## General Fix

`CitationBatchBuilderService` now accepts a PDF citation only when all existing
scope/status/review checks pass, the chunk has non-empty content, and it has a
real page locator plus either a recovered section locator **or the actual
parent document title**. The document-title fallback is a generic traceability
rule for vendor PDFs with page extraction but no heading path; it does not
invent a section.

The fix does not alter candidate retrieval, query normalization, title recall,
document metadata, parsed content, or database rows. HTML rules remain
unchanged. Empty chunks and page-less PDF candidates remain invalid.

`rg` found no target document ID or `Amphenol` special branch in
`backend/app`; the target string exists only in controlled test/runtime
evidence.

## Post-fix Coverage

The formal read-only 10-document coverage run passed. The target obtained its
own valid citation at rank 1 for all required classes:

| Query class | Own citations | Best own rank |
| --- | ---: | ---: |
| Full title | 4 | 1 |
| Model query `20KTL-M3 快速指南` | 4 | 1 |
| Chunk-content query for the Amphenol Helios H4 connector | 1 | 1 |

The target citation uses real chunk
`4d0824c2-6a83-460b-a898-d43c3bb07baf`, page 7, with the target document ID
and formal source hash. No Sungrow citation was returned.

The generalized query `逆变器告警排查` continued to return the real inverter
alarm reference document rather than an unrelated quick guide.

Evidence: `.runtime/task28a-r3d/regression/formal_10_document_rag_coverage.json`
and `.runtime/task28a-r3d/diagnostics/amphenol_retrieval_stage_trace.json`.

## Regression Boundary

Targeted citation tests passed (`5 passed`) and backend `compileall` passed.
However, the frozen 30-case Huawei keyword evaluation is still `NOT_READY`:
Recall@1 `0.392857`, Recall@3 `0.714286`, Recall@5 `0.821429`, MRR
`0.560714`, nDCG@5 `0.626207`, and citation support `0.821429`. Five frozen
cases miss their exact expected citation evidence, even though manufacturer,
product, model, alarm, safety, abstention, scope isolation, and citation
validity gates remain at their required values.

This failure prevents formal full-acceptance. It is a separate frozen
evaluation-label/ranking reconciliation item and was not hidden or solved by
hard-coding this quick guide. Current read-only latency was P50 `6305.524 ms`
and P95 `9166.616 ms`; a like-for-like pre-fix 30-case performance baseline was
not captured during R3D, so no performance non-regression claim is made.

## Result

The Amphenol coverage defect is fixed without formal data mutation, but overall
Task 28A formal RAG acceptance remains
`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL` until the unchanged 30-case
engineering gate is reconciled and meets its frozen thresholds.
