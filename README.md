# Energy-Maintenance

Energy-Maintenance is a PostgreSQL-backed foundation project for renewable energy equipment inspection and maintenance assistance. It focuses on photovoltaic, storage, and power equipment scenarios, including knowledge base metadata, retrieval-style QA, fault diagnosis, maintenance tasks, QA records, devices, basic users, and system status.

## Technology Stack

- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic.
- Database: PostgreSQL with `psycopg`.
- Frontend: Vue 3, Vite, TypeScript, Vue Router, Pinia, Axios, Element Plus.
- Deployment target: native LoongArch + Kylin deployment.
- Docker is not used.

## Backend Startup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger:

```text
http://localhost:8000/docs
```

## Frontend Startup

```bash
cd frontend
npm install
npm run dev
```

Default URL:

```text
http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://127.0.0.1:8000`.

## PostgreSQL Initialization

Create the PostgreSQL database and user manually:

Windows with `psql` in PATH:

```powershell
psql -U postgres -c "CREATE USER energy_user WITH PASSWORD 'energy_password';"
psql -U postgres -c "CREATE DATABASE energy_maintenance OWNER energy_user;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;"
```

Linux:

```bash
sudo -u postgres psql -c "CREATE USER energy_user WITH PASSWORD 'energy_password';"
sudo -u postgres psql -c "CREATE DATABASE energy_maintenance OWNER energy_user;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;"
```

Equivalent SQL:

```sql
CREATE USER energy_user WITH PASSWORD 'energy_password';
CREATE DATABASE energy_maintenance OWNER energy_user;
GRANT ALL PRIVILEGES ON DATABASE energy_maintenance TO energy_user;
```

Then configure `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@localhost:5432/energy_maintenance
```

Run migrations:

```bash
cd backend
alembic upgrade head
```

Quick upload check after backend startup:

```bash
curl -X POST http://localhost:8000/api/knowledge/documents/upload \
  -F "file=@backend/storage/samples/sample_photovoltaic_maintenance.txt" \
  -F "document_type=manual" \
  -F "device_type=inverter" \
  -F "source=local_sample"
```

Knowledge upload settings in `backend/.env`:

```env
UPLOAD_DIR=storage/uploads
MAX_UPLOAD_SIZE_MB=50
ALLOWED_DOCUMENT_EXTENSIONS=txt,md,pdf,docx
DEFAULT_CHUNK_SIZE=1000
DEFAULT_CHUNK_OVERLAP=150
```

## Current API Paths

- `GET /api/health`
- `GET /api/system/info`
- `GET /api/system/status`
- `GET /api/system/statistics`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{user_id}`
- `POST /api/users/{user_id}/enable`
- `POST /api/users/{user_id}/disable`
- `GET /api/devices`
- `POST /api/devices`
- `GET /api/devices/statistics/summary`
- `GET /api/devices/{device_id}`
- `PUT /api/devices/{device_id}`
- `POST /api/devices/{device_id}/retire`
- `GET /api/devices/{device_id}/maintenance-records`
- `POST /api/devices/{device_id}/maintenance-records`
- `GET /api/knowledge/documents`
- `POST /api/knowledge/documents/upload`
- `GET /api/knowledge/documents/{document_id}`
- `GET /api/knowledge/documents/{document_id}/chunks`
- `DELETE /api/knowledge/documents/{document_id}`
- `POST /api/knowledge/documents/{document_id}/reparse`
- `GET /api/knowledge/contributions`
- `POST /api/knowledge/contributions`
- `GET /api/knowledge/contributions/{contribution_id}`
- `PUT /api/knowledge/contributions/{contribution_id}`
- `POST /api/knowledge/contributions/{contribution_id}/submit`
- `POST /api/knowledge/contributions/{contribution_id}/approve`
- `POST /api/knowledge/contributions/{contribution_id}/reject`
- `POST /api/knowledge/contributions/{contribution_id}/request-changes`
- `POST /api/knowledge/contributions/{contribution_id}/convert-to-document`
- `POST /api/knowledge/contributions/{contribution_id}/archive`
- `GET /api/review/knowledge`
- `GET /api/review/knowledge/{document_id}`
- `POST /api/review/knowledge/{document_id}/approve`
- `POST /api/review/knowledge/{document_id}/reject`
- `POST /api/review/knowledge/{document_id}/archive`
- `POST /api/retrieval/query`
- `GET /api/retrieval/records`
- `GET /api/retrieval/records/{trace_id}`
- `POST /api/diagnosis/analyze`
- `GET /api/diagnosis/records`
- `GET /api/diagnosis/records/{trace_id}`
- `GET /api/maintenance/tasks`
- `POST /api/maintenance/tasks`
- `GET /api/maintenance/tasks/statistics/summary`
- `GET /api/maintenance/tasks/assignable-users`
- `GET /api/maintenance/tasks/{task_id}`
- `PUT /api/maintenance/tasks/{task_id}`
- `POST /api/maintenance/tasks/{task_id}/assign`
- `POST /api/maintenance/tasks/{task_id}/start`
- `POST /api/maintenance/tasks/{task_id}/complete`
- `POST /api/maintenance/tasks/{task_id}/cancel`
- `GET /api/media`
- `POST /api/media/upload`
- `GET /api/media/ocr/status`
- `GET /api/media/{media_id}`
- `GET /api/media/{media_id}/content`
- `GET /api/media/{media_id}/ocr`
- `POST /api/media/{media_id}/ocr`
- `GET /api/sop/templates`
- `POST /api/sop/templates`
- `GET /api/sop/templates/{template_id}`
- `PUT /api/sop/templates/{template_id}`
- `POST /api/sop/templates/{template_id}/archive`
- `POST /api/sop/generate`
- `GET /api/sop/executions`
- `POST /api/sop/executions`
- `PUT /api/sop/executions/{execution_id}`
- `GET /api/record-center/overview`
- `GET /api/record-center/search`
- `GET /api/record-center/records/{record_type}/{record_id}`
- `GET /api/record-center/devices/{device_id}/timeline`
- `GET /api/model-gateway/status`
- `POST /api/model-gateway/test`
- `POST /api/model-gateway/chat`
- `GET /api/model-gateway/logs`
- `GET /api/model-gateway/logs/{log_id}`
- `GET /api/kg/overview`
- `GET /api/kg/graph`
- `GET /api/kg/search`
- `GET /api/kg/business-context`
- `GET /api/kg/nodes`
- `POST /api/kg/nodes`
- `PUT /api/kg/nodes/{node_id}`
- `POST /api/kg/nodes/{node_id}/archive`
- `GET /api/kg/edges`
- `POST /api/kg/edges`
- `PUT /api/kg/edges/{edge_id}`
- `POST /api/kg/edges/{edge_id}/archive`
- `GET /api/kg/evidence`
- `GET /api/kg/neighborhood/{node_id}`
- `GET /api/kg/path`
- `GET /api/kg/extraction-runs`
- `GET /api/kg/candidates`
- `POST /api/kg/candidates/{candidate_id}/approve`
- `POST /api/kg/candidates/{candidate_id}/reject`
- `POST /api/kg/extract/from-document/{document_id}`
- `POST /api/kg/extract/from-contribution/{contribution_id}`
- `POST /api/kg/extract/from-record/{record_type}/{record_id}`
- `GET /api/corrections`
- `POST /api/corrections`
- `GET /api/corrections/{correction_id}`
- `POST /api/corrections/{correction_id}/resolve`

## Completed

- FastAPI application startup.
- CORS configuration.
- Unified API router under `/api`.
- Unified response shape.
- Basic exception handling.
- SQLAlchemy models for `users`, `devices`, `knowledge_documents`, `knowledge_chunks`, `maintenance_tasks`, `diagnosis_records`, and `qa_records`.
- Alembic environment, initial migration, and phase-two persistence migration.
- PostgreSQL-backed repositories for knowledge documents, knowledge chunks, maintenance tasks, QA records, diagnosis records, devices, and basic users.
- Knowledge file upload, text extraction, cleaning, chunking, and chunk persistence for `txt`, `md`, `pdf`, and `docx`.
- Vue 3 frontend shell with industrial maintenance platform layout.
- Pages for login, dashboard, system status, knowledge base, retrieval QA, fault diagnosis, and maintenance tasks.
- Axios API calls aligned with the backend API paths.

## PostgreSQL Persistence in This Phase

The following modules now use PostgreSQL persistence:

- Knowledge document list, detail, creation.
- Knowledge document upload and parsing result.
- Knowledge chunk list and creation by document.
- Maintenance task list, detail, creation, and status update.
- QA record persistence and listing.
- Diagnosis record persistence and listing.
- Device and basic user repositories.

## Simulated Logic Still Present

The following modules still use rule-based placeholder logic, but their records are saved to PostgreSQL:

- Retrieval query answer generation.
- Fault diagnosis result generation.
- PDF parsing supports text-based PDFs only; scanned PDFs still require future OCR.

## Next Work

The next stage should add retrieval over persisted chunks, Safety-Gate rule persistence, document review/publish workflow, and richer device/task management pages.
## Task 24B DashVector Note

The current vector RAG enhancement route is DashVector metadata + hybrid retrieval. PostgreSQL remains the source of truth; DashVector is the future online vector recall service. Local tests use `fake_in_memory` and `deterministic_test` only. Real DashVector and real embedding APIs are not called by default and require explicit online acceptance.

## Task 24D Security Hardening Note

Task 24D adds production security checks, CORS configuration from settings, JSON/upload request size limits, lightweight in-memory rate limiting, secret-leak scanning, log sanitization, upload/path traversal checks, and an RBAC matrix script.

The backend exposes only sanitized security status through `/api/system/status`; API keys, Authorization headers, tokens, passwords, local paths, and base64 payloads must not appear in responses or logs. Real DashVector, MIMO, OCR, Cloud LLM, and embedding calls remain opt-in and blocked unless explicitly configured and re-tested. Any previously exposed real keys must be rotated before production use.
