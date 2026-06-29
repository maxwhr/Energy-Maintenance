# Task 18B Knowledge Contribution Closure Report

## Scope

Task 18B implements the frontline knowledge contribution and expert review closed loop for Huawei and Sungrow PV inverter maintenance.

This task does not add Alembic migrations, Docker, SQLite, OCR, embedding, pgvector, or mandatory LLM generation.

## Implemented Flow

```text
engineer creates draft
  -> engineer submits
  -> expert/admin requests changes, approves, or rejects
  -> approved contribution converts to knowledge document
  -> generated chunks become searchable by retrieval
  -> record center traces contribution and related records
```

## Backend

New API group:

```text
/api/knowledge/contributions
```

Implemented actions:

- list
- detail
- create
- update
- submit
- request changes
- approve
- reject
- convert to document
- archive

Conversion writes:

- `knowledge_documents`
- `knowledge_chunks`
- `knowledge_contributions.approved_document_id`
- `knowledge_review_records`

Existing tables were sufficient; no migration was required.

## Frontend

New route:

```text
/knowledge/contributions
```

Capabilities:

- engineer/admin/expert draft form.
- device, diagnosis, task, QA, and media association from existing APIs.
- expert/admin review buttons.
- viewer read-only list/detail.
- converted document trace in contribution detail.

## Record Center

`record_type=knowledge_contribution` is supported in:

- overview count
- search
- detail
- related record lookup
- media evidence lookup

## Demo And Smoke

Updated seed script:

```text
backend/scripts/seed_final_demo_data.py
```

New check script:

```text
backend/scripts/check_contribution_flow.py
```

Smoke extension:

```text
scripts/final_smoke_test.ps1
```

## Verification Commands

```powershell
cd backend
uv run python -m compileall app scripts
uv run python scripts/seed_final_demo_data.py
uv run python scripts/check_contribution_flow.py
uv run python -m alembic -c alembic.ini current

cd ..
npm.cmd --prefix frontend run build
powershell -ExecutionPolicy Bypass -File scripts/final_smoke_test.ps1 -IncludeRetrievalQuery
```

## Known Limits

- Dynamic check records use `Task18B_Flow_` markers and are recognized by `cleanup_dev_test_data.py`.
- Converted contribution content is split by the existing text splitter; no embedding or pgvector index is created.
- Media evidence is linked and previewable, but image content is not interpreted.
- Cloud/local model enhancement remains optional and configuration-dependent.
