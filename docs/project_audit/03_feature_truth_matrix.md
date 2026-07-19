# Feature Truth Matrix

## Status Rules

- `VERIFIED`: current code was exercised safely in this audit.
- `IMPLEMENTED_UNVERIFIED`: end-to-end code exists but the mutating or external path was not run.
- `PARTIAL`: only part of the expected chain exists or only read-side behavior was verified.
- `BROKEN`: current behavior was demonstrated to fail.
- `PLACEHOLDER`: explicit stub/mock-only behavior.
- `DOC_ONLY`: documentation exists without matching implementation.
- `NOT_FOUND`: no implementation found.
- `BLOCKED`: implementation exists but the required environment/service was not used or available.

## Matrix

| ID | Feature | Status | Frontend evidence | Backend/data evidence | Test/runtime evidence | Permission | Main issue | Confidence |
|---|---|---|---|---|---|---|---|---|
| F-001 | Login | VERIFIED | `views/Login.vue`; user store | `routes/auth.py:31-42`; users table | Smoke login and `/auth/me` passed | Public login | Built-in smoke fallback credential accepted | High |
| F-002 | Logout | IMPLEMENTED_UNVERIFIED | Layout/user store action | `routes/auth.py:50-52` | Route exists; not invoked | Auth flow | Stateless response; token is not revoked | High |
| F-003 | Token refresh | NOT_FOUND | No refresh flow found | No refresh endpoint/service found | Not tested | N/A | Long-lived access token only | High |
| F-004 | User management | PARTIAL | `/system/users`, `views/system/Users.vue` | `/api/users`; users table | OpenAPI match; mutation not run | Admin for management | Full current CRUD not exercised | High |
| F-005 | Role management | PARTIAL | Fixed `UserRole` union | Role string and fixed checks | RBAC code inspected | Static roles | No independent role CRUD/model | High |
| F-006 | Permission management | PARTIAL | Route metadata/menu arrays | `require_roles` plus service checks | Selected smoke/RBAC history only | Static RBAC | No dynamic permission policy store | High |
| F-007 | Menu management | NOT_FOUND | Static `router/menus.ts` | No backend menu API | Static inspection | Client-side visibility | Not runtime-configurable | High |
| F-008 | Dashboard/statistics | VERIFIED | `/dashboard` | `/api/system/statistics` and summary services | Smoke passed | Authenticated | No blocking issue found | High |
| F-009 | Device ledger/list | VERIFIED | Device inventory/models/alarms pages | `/api/devices`; devices table | List API smoke passed | Read auth; writes role-limited | Write side not run | High |
| F-010 | Device create/update/status | IMPLEMENTED_UNVERIFIED | Device forms/buttons exist | Device routes/service/repository | 133/133 API static match | Admin/expert/engineer write | No current write verification | Medium |
| F-011 | Device classification | PARTIAL | Huawei/Sungrow/PV options | Domain fields on devices | Static inspection | Authenticated | Static constrained taxonomy, no category admin | High |
| F-012 | Inspection task/result subsystem | NOT_FOUND | No separate inspection module | No distinct inspection task/result API | Not tested | N/A | Maintenance tasks cover related work but are not a dedicated inspection subsystem | Medium |
| F-013 | Fault diagnosis | PARTIAL | `/diagnosis` | `/api/diagnosis/analyze`; diagnosis_records | Record list smoke passed; analyze not run | Operator roles | Current write/answer path unverified | High |
| F-014 | Maintenance work orders | PARTIAL | List/create/detail pages | `/api/maintenance/tasks`; maintenance_tasks | List smoke passed | Role and ownership rules | Mutations not run | High |
| F-015 | Work-order state machine | IMPLEMENTED_UNVERIFIED | Action buttons/API wrappers | `task_workflow_service.py:14-125` | Tests collect; no live mutation | Role/assignee checks | Current transitions not executed | High |
| F-016 | Maintenance workflow orchestration | IMPLEMENTED_UNVERIFIED | `/maintenance-workflow` | workflow routes/services/tables | Code imports; selected 25G tests only | Policy service roles | Current full workflow not executed | Medium |
| F-017 | Review/approval | PARTIAL | `/review` | review routes/service/review tables | Review list smoke passed | Admin/expert mutations | Approval/reject/archive not run | High |
| F-018 | Recheck/acceptance | PARTIAL | Workflow/review surfaces | completion verification and workflow policy services | Tests collect | Expert/admin gates for high risk | No current live acceptance flow | Medium |
| F-019 | Attachments/images | PARTIAL | `/media`, multimodal pages | media routes/tables/local storage | Media API static match | Operator roles | Upload/content write path not run | High |
| F-020 | File upload | IMPLEMENTED_UNVERIFIED | Knowledge/media upload controls | knowledge/media upload services | Static safety inspection | Operator roles | No current upload write; whole-file buffering | High |
| F-021 | Operation/audit logs | PARTIAL | Record center/trace UI | operation_logs, model/external/agent logs | Overview smoke passed | Authenticated summaries | No exhaustive write/log integrity test | High |
| F-022 | Notifications | NOT_FOUND | No notification page/API call | No notification route/model found | Not tested | N/A | Missing feature | High |
| F-023 | Reports/export | NOT_FOUND | No report/export flow found | No report/export route found | Not tested | N/A | Dashboard is not a report/export subsystem | High |
| F-024 | Search | VERIFIED | Knowledge search and record-center search pages | retrieval and record-center search APIs | API matching; read smoke | Authenticated | Retrieval write itself skipped | Medium |
| F-025 | Pagination | VERIFIED | Page response types and controls | Query limits and repository pagination | Static API match and list smoke | Authenticated | No blocking mismatch found | High |
| F-026 | Bulk import | NOT_FOUND | No bulk import UI | No import route found | Not tested | N/A | Upload is per document/media, not bulk import | High |
| F-027 | Knowledge document list/detail | VERIFIED | Documents page | document list/detail/chunks routes and tables | Knowledge list smoke passed | Authenticated | Detail/chunks not separately live-probed here | High |
| F-028 | Knowledge document upload | IMPLEMENTED_UNVERIFIED | Upload form/API | `knowledge_service.py:60-129` | No write invoked | Operator roles | Orphan-file edge case before DB insert | High |
| F-029 | TXT/MD/PDF/DOCX parsing | IMPLEMENTED_UNVERIFIED | Parse status display | `document_parser.py`; pypdf/python-docx | Compile/test collection passed | Service-only | Current fixture upload not repeated | High |
| F-030 | Text chunking | IMPLEMENTED_UNVERIFIED | Chunk viewer | `text_splitter.py`; knowledge_chunks | ORM/DB exact | Service-only | Current write not repeated | High |
| F-031 | Document reparse | IMPLEMENTED_UNVERIFIED | API wrapper/page action | `POST .../reparse`; transactional replacement | Static match | Operator roles | Not run | High |
| F-032 | Document archive/delete | IMPLEMENTED_UNVERIFIED | Archive/delete action | `DELETE /api/knowledge/documents/{id}` | Static match | Role-limited | No live archive test | High |
| F-033 | Knowledge contribution | PARTIAL | Contributions page | contribution routes/service/tables | Smoke list passed | Author/reviewer rules | Mutation/conversion not run | High |
| F-034 | Embedding generation | BLOCKED | Retrieval quality UI | embedding service/adapters | Current config indicates enabled; no call made | Admin/index path | External availability and output dimension not reverified | High |
| F-035 | Vector write/index | BLOCKED | Vector index controls | vector metadata tables, DashVector adapter | No remote write made | Admin/expert writes | External service deliberately not invoked | High |
| F-036 | Vector retrieval | BLOCKED | Retrieval mode controls | DashVector plus PostgreSQL validation | Real route not invoked | Authenticated | Current provider availability unknown | High |
| F-037 | Keyword retrieval | IMPLEMENTED_UNVERIFIED | Assistant/search page | scoring in `retrieval_service.py:559-645` | Static analysis; write query skipped | Operator roles | No current query result captured | High |
| F-038 | Hybrid/reranked retrieval | BLOCKED | Retrieval quality page | fusion/rerank services | Code/test collection exists | Authenticated/admin tuning | Depends on unverified vector/embedding services | High |
| F-039 | RAG/maintenance QA | IMPLEMENTED_UNVERIFIED | Assistant chat/history | `/api/retrieval/query`, QA persistence | Query intentionally skipped in smoke | Operator roles | Current end-to-end QA record creation not run | High |
| F-040 | Source references | IMPLEMENTED_UNVERIFIED | Chat references UI | references built from retrieved chunks; JSONB in qa_records | Static chain confirmed | Same as QA | Current returned references not sampled | High |
| F-041 | SOP templates/executions | PARTIAL | `/sop` | SOP routes/services/tables | Templates/list smoke passed | Operator roles | Generate/update execution not run | High |
| F-042 | Record center/timeline | VERIFIED | `/trace` | overview/search/detail/timeline routes | Overview and record lists smoke passed | All authenticated roles | Large-dataset runtime not repeated | High |
| F-043 | Knowledge graph CRUD | PARTIAL | `/knowledge/graph` | `/api/kg`; PostgreSQL graph tables | KG overview smoke passed | Read all; manage admin/expert in service | Writes not run | High |
| F-044 | KG production grounding | PARTIAL | Graph/trace surfaces | production scope and grounding services | Current R2 report: 68 facts, one grounded edge | Human review gates | Too sparse for production enrichment | High |
| F-045 | Media OCR | BLOCKED | Media OCR controls | OCR service/provider adapters | Runtime flag disabled; no OCR call | Role-limited | Current real recognition unavailable | High |
| F-046 | Multimodal AI analysis | BLOCKED | Multimodal pages | provider gateway/analysis services | No real external call | Expert/admin for real/mock modes | Provider availability unverified | High |
| F-047 | Agent runtime/tools | PARTIAL | Agent workbench | agent routes, 16+ tool services and tables | OpenAPI/static match; no agent run here | Tool/approval policies | Current write/external tools not executed | Medium |
| F-048 | Model gateway | PARTIAL | Admin model page | status/test/chat routes and adapters | Status smoke passed | Admin management | Real model call deliberately not made | High |
| F-049 | System health/status | VERIFIED | `/system` | health/status/statistics endpoints | Health/status smoke passed; DB online | Admin UI, health public | Database service persistence risk remains | High |
| F-050 | System configuration | PARTIAL | Status/provider views | Environment-driven settings | Sanitized settings import passed | Admin for provider checks | No configuration CRUD; restart required | High |
| F-051 | Database backup | IMPLEMENTED_UNVERIFIED | No UI | `deploy/loongarch/scripts/backup_before_upgrade.sh` | Static unit/dry-run tests only | Host operator | Not executed against current database | High |
| F-052 | Native deployment scripts | IMPLEMENTED_UNVERIFIED | N/A | `deploy/loongarch/` | Seven static Task 25G tests passed | Host operator | No real LoongArch/Kylin host | High |
| F-053 | Frontend production build | VERIFIED | 33 routes | Static SPA served by backend | typecheck and temp production build passed | Route guards | Generated assets/worktree need clean policy | High |
| F-054 | API contract matching | VERIFIED | 133 detected calls | 233 OpenAPI paths | 133 matched; 0 missing/wrong/fake | Backend remains authority | Success code convention is dual | High |

## Summary By Status

The application has a broad, coherent implemented surface. Safe read-side core APIs, schema alignment and the frontend build are verified. Most remaining uncertainty is concentrated in mutating workflows, external AI/vector providers, physical LoongArch deployment and production-quality knowledge-graph grounding. No feature was classified `BROKEN` from the safe checks performed; this does not mean the unexecuted write paths are proven correct.

