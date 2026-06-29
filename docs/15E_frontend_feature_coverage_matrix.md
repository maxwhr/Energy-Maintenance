# Task 15E / Task 16 / Task 17B Frontend Feature Coverage Matrix

This matrix records the delivery-facing coverage after `cupProject` was merged into `Energy-Maintenance/frontend` and Task 16 hardening started.

Status values:

- `passed`: frontend entry and backend API wiring are present.
- `partial`: core flow is present, but at least one requested button, detail view, or edge workflow is still incomplete.
- `blocked`: backend/API/environment prevents meaningful frontend verification.

| Backend module | Frontend entry | Status | Notes |
| --- | --- | --- | --- |
| Auth login / me / logout | `/login`, route guard, layout user menu | passed | Login, token persistence, `/api/auth/me`, logout, and protected-route restore were verified in Task 15B. |
| Users list/create/edit/enable/disable | `/system/users` | passed | Admin-only list, create, edit, enable, and disable are wired to `/api/users`. |
| Devices list/create/edit/retire/detail/maintenance records/statistics | `/device/inventory` | passed | Inventory form, filters, detail, retire, maintenance record creation, and statistics are present. Task 16 replaced raw device JSON with field cards. |
| Knowledge upload/list/detail/chunks/reparse/archive | `/knowledge/documents` | passed | Upload, list, chunk view, reparse, and archive/delete actions are present. |
| Frontline knowledge contribution/review/convert | `/knowledge/contributions` | passed | Task 18B adds engineer draft/submit/edit, expert/admin request-changes/approve/reject/convert/archive, viewer read-only access, media association, and converted-document traceability. |
| Media upload/list/detail/selection | `/media`, knowledge, retrieval, diagnosis, task detail | passed | Task 17B aligns upload types to jpg/jpeg/png/webp, adds device/fault/alarm metadata, authenticated preview, existing-media selection, uploader/OCR status display, and task/QA/diagnosis linkage. |
| Retrieval query/records/detail/model enhancement | `/assistant/chat`, `/assistant/history`, `/knowledge/search` | passed | Task 17B limits formal retrieval to approved active parsed knowledge, adds device/media selection, persists media summaries in existing JSONB, and displays media evidence without inferring image content. |
| Diagnosis analyze/records/detail/media/history/model enhancement | `/diagnosis` | passed | Task 17B adds upload or selection of existing images, backend media validation, response preview, OCR-disabled notice, and diagnosis/record-center traceability. |
| SOP templates/create/edit/archive/generate/executions | `/sop` | passed | Task 17B adds diagnosis selection and diagnosis-media display. SOP completion now records user-entered execution notes, abnormal conditions, and review result instead of a fixed one-step conclusion. |
| Maintenance tasks list/create/detail/edit/assign/start/complete/cancel/statistics | `/workorder/list`, `/workorder/create`, `/workorder/:id` | passed | Task 17B expands completion input to summary, root cause, actual solution, used parts, safety verification, follow-up flag, and task-linked image evidence using existing fields only. |
| Record center overview/search/detail/device timeline | `/trace` | passed | Structured detail, related records and timeline remain available. Task 17B adds related media summaries and authenticated previews for QA, diagnosis, task, maintenance, SOP execution, and media records. |
| Review knowledge list/detail/approve/reject/archive | `/review` | passed | Knowledge review list and approve/reject/archive actions are present. |
| Corrections create/list/detail/resolve | `/review/corrections` | passed | Create, list, detail, accept, and reject are present. Task 16 changed correction detail from raw JSON to structured output comparison. |
| Model gateway status/test/chat/logs/detail | `/model-service` | passed | Status, test, chat, logs, and log detail are present. Cloud/local model availability is configuration-dependent and must not be reported as passed unless configured. |
| System health/info/status/statistics | `/system` | passed | System page calls status/statistics/model gateway. Task 16 changed database status to a real backend connectivity check and structured frontend display. |
| Knowledge graph overview/nodes/edges/candidates/runs/evidence/neighborhood/graph/path | `/knowledge/graph` | passed | Task 18C adds PostgreSQL-backed graph management. Task 18D adds lightweight graph visualization, node/edge evidence lookup, neighborhood expansion, and path query. Viewer is read-only; expert/admin can manage graph data and review candidates. |

Known limitations:

- `frontend` is the only active frontend source tree. `frontend_legacy_before_cupProject_*` is a temporary backup and must not be included in final release packaging.
- `backend/static/frontend` is generated build output installed by `backend/scripts/build_and_install_frontend.ps1`; it is not the source of truth.
- `cloud_openai` and `local_llama_cpp` remain optional and configuration-dependent.
- Media upload and evidence association are available. OCR automatic recognition, image fault recognition, multimodal semantic matching, pgvector, and embeddings remain deferred and are not claimed as completed capabilities.
- Knowledge graph business enhancement is available for retrieval, diagnosis, SOP, and record-center detail display when active graph context exists. Real model-based graph extraction, external graph databases, pgvector, and embedding-based graph retrieval remain deferred.

Task 16A browser verification on June 15, 2026 confirmed the admin edit/reassignment entry points, record detail and device timeline drilldown, viewer read-only task access, viewer record-detail access, and viewer denial for `/review` and `/model-service`.

Task 17B browser verification confirmed the diagnosis and retrieval media pickers, knowledge-page media entry, authenticated media detail preview, admin access to the media workflow, and viewer redirection to `/403` for media management and review routes.

Task 18B adds `/knowledge/contributions` as the frontline knowledge contribution entry. The route is visible to admin/expert/engineer/viewer; viewer access is read-only, while write and review actions are role-gated by the backend.

Task 18C adds `/knowledge/graph` as the knowledge graph foundation entry. The page is visible to all roles; viewer is read-only, expert/admin can manage graph data and review extraction candidates, and engineer can read graph data.

Task 18D extends `/knowledge/graph` with lightweight visualization and path query, and adds graph-enhanced context display to `/assistant/chat`, `/diagnosis`, `/sop`, and `/trace`. Business pages only display graph context returned by the backend; they do not fabricate graph evidence.
