# Actual System Architecture

## 1. Product Position Confirmed By Code

The implemented system is a Huawei/Sungrow PV-inverter maintenance workbench with document ingestion, traceable retrieval, diagnosis, SOP/task workflows, record tracing, media evidence, agents and PostgreSQL-backed knowledge graph capabilities. It is broader than the first-stage shell, but remains centered on PV inverter maintenance data and workflows.

## 2. Runtime Topology

```text
Vue SPA / backend static files
        |
        | /api + JWT Bearer
        v
FastAPI on 127.0.0.1:8012
        |
        +--> SQLAlchemy Session --> PostgreSQL 16.14 on 127.0.0.1:55432
        +--> local backend storage (documents/media)
        +--> optional external provider adapters
             - Cloud text/vision/MIMO/OCR
             - Embedding API
             - DashVector
             - local llama.cpp
```

No Redis, message queue, external object storage or Neo4j connection was found.

## 3. Backend Layers

The dominant path follows `api -> service -> repository -> model`:

- Route registration: `backend/app/main.py:66-106`.
- Authentication dependency and role helpers: `backend/app/core/dependencies.py:30-66`.
- Services: `backend/app/services/`.
- Repositories: `backend/app/repositories/`.
- ORM models: `backend/app/models/`.
- Request/response schemas: `backend/app/schemas/`.
- Database sessions: `backend/app/core/database.py`.

Some route modules define local `ok/fail` helpers rather than the shared response helper. This does not break the frontend because the interceptor accepts both code 0 and 200, but it weakens API uniformity.

## 4. Public API Groups

The OpenAPI document contains 233 paths. `main.py` mounts 25 route groups under `/api`, including:

- health, system and authentication;
- users and devices;
- knowledge documents and contributions;
- knowledge graph and vector search;
- retrieval, diagnosis and SOP;
- maintenance tasks and maintenance workflows;
- media, multimodal evidence and multimodal cases;
- record center, review and corrections;
- model gateway and external API providers;
- agent runtime and business tools.

The public prefix remains `/api`; no active frontend call requires `/api/v1`.

## 5. Frontend Architecture

- SPA entry: `frontend/src/main.ts`.
- Router and role guard: `frontend/src/router/index.ts:213-243`.
- Menu visibility: `frontend/src/router/menus.ts:37-145`.
- Central Axios client: `frontend/src/utils/request.ts:24-71`.
- Authentication state: Pinia user store and JWT in localStorage.
- API modules: `frontend/src/api/`.
- Views: 33 routed pages under `frontend/src/views/`.

The client uses relative `/api` requests and handles both `{code: 0}` and `{code: 200}` responses.

## 6. Authentication And Authorization Flow

1. `POST /api/auth/login` validates credentials and issues an HS256 bearer token.
2. The frontend stores the token in localStorage and attaches it to Axios requests.
3. `GET /api/auth/me` restores the current user.
4. Router metadata enforces page-level role checks.
5. Backend dependencies enforce authentication and many route-level role checks.
6. Sensitive services such as knowledge graph, contribution review and task transitions repeat permission checks at the service layer.

Passwords are PBKDF2-SHA256 hashed (`backend/app/core/security.py:14-57`). Logout is stateless and does not revoke an issued token.

## 7. Core Knowledge And Retrieval Flow

```text
Upload -> extension/size/path checks -> local file
       -> txt/md/pdf/docx parser -> chunks
       -> knowledge_documents + knowledge_chunks in PostgreSQL
       -> review_status gate

Question -> query understanding/expansion
         -> PostgreSQL keyword candidates
         -> optional Embedding + DashVector candidates
         -> fusion/rerank/refinement
         -> citation validation + rule/model answer boundary
         -> qa_records + trace/log records
```

Evidence:

- Upload and processing: `backend/app/services/knowledge_service.py:60-129,245-299`.
- Hybrid retrieval and fallback: `backend/app/services/retrieval_service.py:115-207`.
- Real-source references and QA persistence: `backend/app/services/retrieval_service.py:226-337,806-840`.
- Vector test boundary: `backend/app/services/vector_index_service.py:535-669`.

## 8. Business Workflow Flow

Diagnosis, SOP, tasks, approvals, media evidence, agents and corrections are persisted through dedicated services and repositories. Task status changes are guarded by `TaskWorkflowService`, while the newer maintenance workflow uses `MaintenanceWorkflowPolicyService` for stage, role and safety decisions.

Evidence:

- `backend/app/services/task_workflow_service.py:14-125`
- `backend/app/services/maintenance_task_service.py:96-263`
- `backend/app/services/maintenance_workflow_policy_service.py:82-277`
- `backend/app/services/maintenance_workflow_service.py:33-458`

## 9. Data Storage

- 57 ORM-managed application tables.
- 58 public PostgreSQL tables including `alembic_version`.
- 15 linear Alembic revisions, current at `20260712_0015`.
- JSONB is used for references, retrieved chunks, provider summaries, graph metadata and workflow evidence.
- Local filesystem stores uploaded source files and media; the database stores metadata and relative paths.
- DashVector stores remote vector records when explicitly enabled; PostgreSQL remains the authoritative business record.

## 10. Deployment Structure

`deploy/loongarch/` provides native installation scripts, dependency manifests, systemd/Nginx templates, backup, migration, health check, atomic release and rollback support. The systemd unit runs Uvicorn on 8012 with restart-on-failure. Production frontend assets are prebuilt so Node/npm are not runtime dependencies.

## 11. Architectural Fractures

1. The running architecture is not reproducible from Git because a large fraction of current code and seven migrations are untracked.
2. The test suite lacks a mandatory isolated database boundary even though integration tests perform writes.
3. Response success codes use both 0 and 200.
4. The frontend menu role hierarchy hides some routes that the router and backend permit for viewers.
5. External AI/vector paths are configuration-sensitive and cannot be considered current-operational without controlled real-call acceptance.
6. Knowledge graph storage and orchestration exist, but current Chinese production grounding is too sparse for production answer enrichment.

## 12. Documentation Differences

- Root README line 3 describes a generic renewable/storage/power platform, conflicting with the Huawei/Sungrow PV-inverter first-version scope in `AGENTS.md`.
- README files combine historical task reports with current operating instructions, making current capability status hard to distinguish.
- Current source/package naming still contains `cupproject`.
- Historical reports contain passed results from earlier configurations; they are evidence snapshots, not proof of current provider availability.

