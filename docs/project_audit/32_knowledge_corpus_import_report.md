# Task 28A Knowledge Corpus Import Report

## Result

- Status: `APPLY_COMPLETED`
- Target database: `energy_maintenance_task27a_test`
- Manifest documents: `21`
- Selected documents: `15`
- Imported and parsed documents: `15`
- Stored knowledge chunks: `1,255`
- Failed documents: `0`
- Vector rebuild: not executed

`backend/scripts/import_competition_knowledge_corpus.py` verified the selected source files by project path, size, and SHA-256 before using the real `KnowledgeService`, parser, chunker, repositories, and review service. Test uploads were stored only under `backend/storage/tmp/task28a_test_uploads`.

## Approval and Scope Evidence

| Group | Documents | Parse status | Review status | Retrieval eligibility |
| --- | ---: | --- | --- | --- |
| Huawei SUN2000 | 10 | all `parsed` | all `approved` | eligible in the Huawei competition scope |
| Sungrow future scope | 5 | all `parsed` | all `pending_review` | excluded |

The explicit Sungrow gate check returned:

- `sungrow_pending_review_count=5`
- `sungrow_all_pending_review=true`
- `sungrow_citation_count=0`
- `sungrow_retrieved_chunk_count=0`
- `persist_result=skipped_preview`

No Sungrow document entered the Huawei scope, no vector index was rebuilt, and no formal database was written.

## Import Safety

- The derived Markdown alias remains excluded from duplicate chunk ingestion.
- Six manifest entries outside the selected 15 remain outside automatic test import.
- Source SHA-256 is used for resume/idempotency.
- Formal import remains gated and was not requested in Task 28A-R2C.
