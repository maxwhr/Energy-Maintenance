# Cross-layer Consistency Audit

## 1. Frontend To Backend API

The current static integration scan found:

- OpenAPI paths: 233
- Frontend API functions/calls detected: 133
- Matching backend method/path pairs: 133
- Missing/wrong pairs: 0
- Frontend fake/mock-success hits: 0

Evidence: `backend/scripts/check_real_frontend_api_integration.py` executed against the current OpenAPI and `frontend/src`.

The frontend consistently uses the centralized `/api` Axios client (`frontend/src/utils/request.ts:24-35`). No active frontend path was found using `/api/v1`.

## 2. Response Contract

The response envelope is consistently shaped as `code/message/data`, but success code semantics are dual:

- Shared schema helper uses code 200: `backend/app/schemas/common.py:6-23`.
- Authentication and devices use code 0: `backend/app/api/routes/auth.py:15-28`, `backend/app/api/routes/devices.py:25-38`.
- Frontend explicitly accepts both: `frontend/src/utils/request.ts:38-49`.

This is operationally compatible but contradicts the documented single convention and increases client/test complexity.

## 3. ORM, Alembic And PostgreSQL

Read-only metadata comparison showed:

- 57 application tables in `Base.metadata`.
- 58 public PostgreSQL tables, with only `alembic_version` not represented as an ORM model.
- No table missing from PostgreSQL.
- No compared column missing or extra.
- Single Alembic head/current at `20260712_0015`.

The current database and working tree are aligned. Delivery consistency is nevertheless broken because migrations 0009-0015 and associated model/service code are untracked.

## 4. Domain And Status Consistency

### Confirmed consistent

- First-version manufacturers and PV-inverter domain checks are enforced in knowledge upload (`knowledge_service.py:361-376`).
- Task workflow state transitions are centralized (`task_workflow_service.py:51-125`).
- New maintenance workflow decisions centralize stage/role/safety policy (`maintenance_workflow_policy_service.py:82-277`).
- Parse state enforces non-empty chunks before `parsed` (`knowledge_service.py:252-299`).
- Parse failure removes chunks, sets `failed`, zeroes `chunk_count`, records an error and commits (`knowledge_service.py:385-400`).
- QA references/retrieved chunks/confidence/trace fields are persisted to PostgreSQL (`retrieval_service.py:806-840`, `models/record.py:14-34`).

### Partial/inconsistent

- Root README line 3 describes photovoltaic, storage and power-equipment scope, while `AGENTS.md` limits first-version scope to Huawei/Sungrow PV inverters.
- Frontend menu parent roles can hide viewer-accessible child routes: `/review` child and `/agents/workbench` are declared for viewers, but their parents exclude viewers (`frontend/src/router/menus.ts:74-83,114-122`). The router itself permits those pages (`frontend/src/router/index.ts:101-104,143-146`).
- Frontend package name remains `cupproject` even though product identity is Energy-Maintenance.

## 5. Permission Consistency

### Positive findings

- Authentication dependency rejects missing/invalid users and disabled accounts.
- Knowledge graph route handlers pass the current user into the service; write methods call `_require_manager`, restricting writes to admin/expert (`knowledge_graph_service.py:175-299,326-408,1110-1117`).
- Knowledge contributions enforce author/reviewer roles in the service (`knowledge_contribution_service.py:37-38,438-466`).
- Review mutations use route-level `require_roles("admin", "expert")` and repeat reviewer-role checks in the service.
- Maintenance task mutation routes and service/workflow rules restrict roles, assignment and transitions.

### Remaining boundary gaps

- Client route/menu permissions are usability controls only; backend role enforcement remains the authority.
- Roles and permissions are hard-coded strings rather than database-managed policies.
- Logout does not revoke tokens, so clearing local state is the only immediate logout effect.

## 6. Transaction And File Consistency

### Confirmed

- Parse/chunk replacement and document status update are committed together after the initial document row exists (`knowledge_service.py:118-129,245-299`).
- Parse failure rolls back the failed transaction, deletes managed chunks, stores failure state and commits (`knowledge_service.py:385-400`).
- Review transitions wrap status/audit writes in commit/rollback (`review_service.py:238-276`).
- Contribution-to-document conversion uses one transaction and rollback (`knowledge_contribution_service.py:259-359`).

### Risks

- The source file is written before title validation and before the initial document insert (`knowledge_service.py:79-84,301-331`). Empty title or database insert failure can leave an orphan file.
- Uploads are fully read into memory before size rejection (`knowledge_service.py:310-315`; similar media path), increasing memory pressure under concurrent 50 MB uploads.
- Full test execution is not transactionally isolated from the configured database.

## 7. File And Upload Safety

Knowledge upload checks extension, empty content, size, basename sanitization, UUID storage name, resolved path containment and exclusion from the frontend directory (`knowledge_service.py:301-359`). Media processing additionally validates type/decoding in `media_service.py`. No path traversal route was found in the inspected upload flow.

## 8. Delete/Archive Semantics

Core knowledge, review, graph, SOP and workflow modules predominantly use archive/status transitions rather than arbitrary hard delete. Exact semantics are module-specific; there is no single cross-system soft-delete mixin. This is maintainable at current scale but makes global retention policies harder to prove.

## 9. Consistency Verdict

| Area | Verdict |
|---|---|
| Frontend path/method vs OpenAPI | VERIFIED |
| ORM vs current PostgreSQL | VERIFIED |
| Alembic chain | VERIFIED in working tree, unreproducible from Git |
| RBAC critical paths | IMPLEMENTED and statically verified |
| Mutating transaction behavior | IMPLEMENTED_UNVERIFIED with targeted static confirmation |
| Status naming | Mostly consistent; no blocking mismatch found |
| Unified response success code | PARTIAL, dual 0/200 convention |
| Git/delivery consistency | BROKEN for reproducible delivery |

