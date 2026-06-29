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
- `GET /api/knowledge/documents`
- `POST /api/knowledge/documents`
- `POST /api/knowledge/documents/upload`
- `GET /api/knowledge/documents/{document_id}`
- `GET /api/knowledge/documents/{document_id}/chunks`
- `POST /api/knowledge/documents/{document_id}/chunks`
- `DELETE /api/knowledge/documents/{document_id}`
- `POST /api/knowledge/documents/{document_id}/reparse`
- `POST /api/retrieval/query`
- `POST /api/maintenance/diagnose`
- `GET /api/maintenance/tasks`
- `POST /api/maintenance/tasks`
- `GET /api/maintenance/tasks/{task_id}`
- `PATCH /api/maintenance/tasks/{task_id}/status`
- `GET /api/records/qa`
- `GET /api/records/diagnosis`

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
