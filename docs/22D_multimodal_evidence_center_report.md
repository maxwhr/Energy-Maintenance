# Task 22D Multimodal Evidence Center Report

## Scope

Task 22D adds the database and service foundation for a multimodal evidence center.

The center provides a unified place for media processing jobs, OCR result records, multimodal AI analysis records, evidence links, and media-level multimodal summaries.

This task does not perform real OCR, real mimo-2.5 calls, real cloud vision calls, local model inference, image understanding, pgvector, embedding, Neo4j, or Docker-based deployment.

## Database

Migration:

- `backend/alembic/versions/20260601_0006_add_multimodal_evidence_center.py`
- `down_revision = 20260601_0005`

New tables:

- `media_processing_jobs`
- `media_ocr_results`
- `media_ai_analyses`
- `media_evidence_links`

The migration was executed on the local PostgreSQL instance at `127.0.0.1:55432`.

## Backend API

New API prefix:

- `/api/multimodal`

Endpoints:

- `GET /api/multimodal/media/{media_id}/jobs`
- `POST /api/multimodal/media/{media_id}/jobs`
- `GET /api/multimodal/jobs/{job_id}`
- `POST /api/multimodal/jobs/{job_id}/cancel`
- `GET /api/multimodal/media/{media_id}/ocr-results`
- `GET /api/multimodal/ocr-results/{result_id}`
- `GET /api/multimodal/media/{media_id}/analyses`
- `GET /api/multimodal/analyses/{analysis_id}`
- `POST /api/multimodal/analyses/{analysis_id}/review`
- `GET /api/multimodal/evidence-links`
- `POST /api/multimodal/evidence-links`
- `GET /api/multimodal/media/{media_id}/summary`

## Expected Blocked Behavior

`POST /api/multimodal/media/{media_id}/jobs` creates real database jobs.

For `job_type=ocr`, the service reads the External API Provider Gateway route for `media_ocr`. If OCR is disabled or not configured, it creates a `blocked` job and writes a dry-run/blocked external API log.

For `job_type=multimodal_analysis`, the service reads the route for `media_mimo_analysis`. If `mimo_2_5` or fallback vision providers are not configured, it creates a `blocked` job and writes a dry-run/blocked external API log.

For `job_type=combined`, the service records both OCR and multimodal dry-run status and creates a blocked combined job.

No external API is called in Task 22D.

## Review and Evidence Links

Expert/admin users can review `media_ai_analyses` by changing `human_review_status` to:

- `accepted`
- `rejected`
- `revised`

The review operation does not overwrite `raw_response_json`.

Evidence links connect media evidence to source records such as:

- retrieval
- diagnosis
- SOP
- maintenance task
- knowledge contribution
- knowledge document
- record center
- agent run
- agent artifact
- correction

## Agent Tool Integration

Updated tools:

- `media_lookup`: returns media metadata plus compact multimodal summary counts.
- `media_ocr`: first reads latest succeeded `media_ocr_results`; if absent, reads latest OCR job state and then returns provider blocked/dry-run status.
- `media_mimo_analysis`: first reads latest accepted analysis; if absent, reads latest pending analysis; if absent, reads job/provider blocked state.

Agent tools do not return local file paths or binary image content.

## Verification

Executed verification:

- `uv run python -m compileall app scripts`
- `uv run python -m alembic -c alembic.ini heads`
- `uv run python -m alembic -c alembic.ini current`
- `uv run python -m alembic -c alembic.ini upgrade head`
- `uv run python scripts\check_multimodal_evidence_flow.py`
- `uv run python scripts\check_external_api_gateway_flow.py`
- `uv run python scripts\check_agent_business_tools_flow.py`
- `npm.cmd install`
- `npm.cmd audit`
- `npm.cmd run build`
- `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010`

Current local environment:

- Backend: `http://127.0.0.1:8010`
- PostgreSQL: `127.0.0.1:55432`
- Alembic current: `20260601_0006`

## Remaining Work

- Real mimo-2.5 adapter connection is not implemented.
- Real OCR recognition through the evidence center is not implemented.
- Full multimodal evidence frontend UI is not implemented.
- Diagnosis, SOP, and knowledge curation agents do not yet consume multimodal evidence deeply beyond media tools.

Recommended next task:

- Task 22E: mimo-2.5 multimodal adapter integration position and configuration acceptance.
## Task 22E Follow-up

Task 22E connects the evidence center to the adapter contract:

- dry-run jobs create job records without machine results;
- mock-run jobs can persist explicitly mocked AI analysis or OCR results;
- agent media tools can read accepted or mocked evidence-center results;
- all mocked results remain auxiliary, not-for-production evidence.

## Task 22F Follow-up

Task 22F adds the frontend evidence-center route `/multimodal`.

The page exposes media selection, provider status, processing jobs, OCR results, AI analysis review, evidence links, and Agent Run dry-run entry. It uses existing `/api/multimodal`, `/api/external-apis`, `/api/media`, and `/api/agents` APIs and does not add a database migration.
