# Task 24B DashVector Hybrid RAG Report

## Scope

Task 24B recovers the selected vector RAG route:

- PostgreSQL remains the primary business database and source of truth.
- DashVector is the target online vector database for vector recall.
- Local verification uses `deterministic_test` embeddings and `fake_in_memory` vector adapter.
- Keyword retrieval and vector retrieval are merged by hybrid scoring.
- Retrieved vector hits must be verified again against PostgreSQL approved / parsed / active document and chunk status.

This task does not package delivery artifacts and does not call real DashVector or real embedding APIs by default.

## Recovery From Wrong Direction

The temporary pgvector direction was corrected. The final implementation does not use:

- `CREATE EXTENSION vector`
- local PostgreSQL `vector` columns
- `knowledge_chunk_embeddings`
- `embedding_runs`
- pgvector `<=>` SQL retrieval
- Milvus / Qdrant / Chroma / FAISS / Weaviate

The active Task 24B API is `/api/vector-search`, not `/api/embeddings`.

## Database Metadata

Migration: `20260601_0007_add_dashvector_rag_metadata.py`

Tables:

- `knowledge_chunk_vector_indexes`
- `vector_index_runs`

These tables store DashVector index metadata and run records only. Raw vectors are not stored in PostgreSQL.

## Security Boundaries

- `backend/.env` was not modified.
- `.env.example` contains placeholders only.
- API keys are not returned by APIs or scripts.
- Real DashVector and real embedding calls require explicit opt-in and complete environment configuration.
- `fake_in_memory` is local test only and must not be claimed as real DashVector.
- `deterministic_test` embedding is local test only and must not be claimed as production semantic embedding.

## Hybrid Retrieval

Retrieval supports:

- `keyword`
- `vector`
- `hybrid`

Response diagnostics include retrieval mode, vector availability, vector backend, fallback state, score breakdown, and warnings. If vector retrieval is unavailable, the service falls back to keyword retrieval and records that in the response and `qa_records`.

## Knowledge Curator

`knowledge_curator_agent` duplicate risk now reads retrieval diagnostics:

- `duplicate_check_mode`
- `vector_available`
- `vector_backend`
- `fallback_reason`
- `max_similarity`

Fallback results are not represented as semantic vector certainty.

## Current Known Limits

- Real DashVector online acceptance is not executed in this task.
- Real embedding API acceptance is not executed in this task.
- Local fake vector search is process-local and only supports repeatable test flows.
- Production performance depends on DashVector collection configuration and real embedding model quality.

## Finalize Verification

Task 24B-DashVector-Finalize restored the local verification environment and completed the DashVector-route acceptance checks without adding new product features or creating a delivery package.

### Environment Recovery

- PostgreSQL was restored on `127.0.0.1:55432` by starting the existing local PostgreSQL data directory in standalone mode.
- SQLAlchemy connection succeeded against `energy_maintenance` as `energy_user`.
- Backend was started on `http://127.0.0.1:8010`.
- `/api/health`, `/api/system/status`, and `/openapi.json` were reachable from the running backend.

### Migration Result

- Alembic heads: `20260601_0007 (head)`.
- Alembic current before upgrade: `20260601_0006`.
- Alembic upgrade executed from `20260601_0006` to `20260601_0007`.
- Alembic current after upgrade: `20260601_0007 (head)`.
- Database vector metadata tables present:
  - `knowledge_chunk_vector_indexes`
  - `vector_index_runs`
- Database table inspection did not show the old pgvector table names `knowledge_chunk_embeddings` or `embedding_runs`.

### DashVector Local Verification

- `check_dashvector_config_status.py`: passed.
- `check_dashvector_hybrid_rag_flow.py`: passed.
- Local verification used `deterministic_test` embeddings and `fake_in_memory` vector adapter.
- Approved / parsed / active knowledge chunks participated in retrieval.
- Pending and archived knowledge were excluded by PostgreSQL status verification.
- Viewer permission verification used the restored `8010` backend when `TestClient` was unavailable, and viewer-triggered vector indexing was blocked.
- Retrieval returned real PostgreSQL-backed references and retrieved chunks.
- No real DashVector API call was made.
- No real embedding API call was made.
- No raw vectors were returned in API responses.

### Regression Verification

The following regression scripts were executed against the restored `8010` backend and `55432` PostgreSQL database:

- `check_knowledge_curator_agent_flow.py`: passed.
- `check_agent_artifact_conversion_flow.py`: passed.
- `check_diagnosis_sop_task_agent_flow.py`: passed.
- `check_multimodal_evidence_agent_flow.py`: passed.
- `check_external_api_gateway_flow.py`: passed.
- `final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`: passed, `failed = 0`.

### Frontend Verification

- `npm.cmd install`: passed.
- `npm.cmd audit`: passed with `0 vulnerabilities`.
- `npm.cmd run build`: passed.
- `backend/scripts/build_and_install_frontend.ps1`: passed and installed 59 static frontend files into `backend/static/frontend`.

### OpenAPI Verification

OpenAPI includes the Task 24B vector-search routes:

- `/api/vector-search/status`
- `/api/vector-search/documents/{document_id}/index`
- `/api/vector-search/test-query`

The protected `/api/vector-search/status` endpoint returned `401` without authentication and `200` with the admin token, which confirms the route is registered and permission-protected.

### No-Package Verification

- No delivery zip was generated in this task.
- `delivery/` kept its existing historical files and timestamps.
- `delivery_staging/` kept its existing historical timestamp.
- `git status --short -- delivery delivery_staging` returned no changes.
- `Compress-Archive` was not executed.

### Security Notes

- `backend/.env` was not modified.
- No API key value was printed.
- Real DashVector and real embedding online acceptance remain blocked until fresh credentials are configured and the leaked prior key is rotated.
- `fake_in_memory` and `deterministic_test` remain local validation utilities only and must not be described as real DashVector or production embedding.

## Next Step

Task 24C can perform real external API online acceptance only after explicit user approval and key rotation. Because a DashVector key appeared in prior conversation context, that key should be treated as leaked and rotated before real use.
