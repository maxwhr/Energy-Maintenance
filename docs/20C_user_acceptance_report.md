# Task 20C User Acceptance and Usability Review

## 1. Trial Environment

- Task: Task 20C - 真实使用者视角全流程试用与可用性验收
- Review time: 2026-06-29 19:11-19:20 +08:00
- Project root: `D:\Work Space\Energy-Maintenance`
- Git commit at review start: `c28ae4f`
- Backend used for trial: `http://127.0.0.1:8010`
- Frontend used for trial: FastAPI static SPA served from the same backend.
- Database: PostgreSQL online through local native PostgreSQL process.
- Browser interaction: executed with the in-app browser against `http://127.0.0.1:8010`.
- Port note: `http://127.0.0.1:8000/api/health` was unavailable during this trial. Starting a second backend on `8000` failed, so the already running Energy-Maintenance instance on `8010` was used and verified.
- Migration note: `alembic upgrade head` was not executed.
- Code change note: no business code was changed.

## 2. Trial Accounts

The trial used the existing local `admin` account and temporary `Task20C_` role accounts created through the API for usability testing. Password values are intentionally not recorded in this report.

| Account | Role | Trial usage | Final status |
| --- | --- | --- | --- |
| `admin` | admin | Browser login, dashboard/system/model/review/user-management route trial, API setup | retained |
| `Task20C_engineer` | engineer | API workflow trial: device, media, contribution, retrieval, diagnosis, SOP, task | disabled |
| `Task20C_expert` | expert | API workflow trial: approve/convert contribution, cleanup/archive | disabled |
| `Task20C_viewer` | viewer | API and browser read-only/403 route trial | disabled |

## 3. Browser Trial Summary

Browser checks were performed on the login page, admin dashboard, core admin routes, and viewer-restricted routes.

### Admin Browser Flow

- Login page loaded with clear Chinese positioning for Huawei/Sungrow PV inverter maintenance.
- Admin login through the visible login form succeeded.
- Dashboard loaded without blank page or console error.
- Main menu labels were understandable and Chinese-first.
- Core routes opened successfully:
  - `/dashboard`
  - `/device/inventory`
  - `/knowledge/documents`
  - `/knowledge/contributions`
  - `/assistant/chat`
  - `/diagnosis`
  - `/sop`
  - `/workorder/list`
  - `/trace`
  - `/media`
  - `/knowledge/graph`
  - `/model-service`
  - `/system`
  - `/review`
  - `/system/users`
- No empty page was observed in these route checks.
- No browser console error was observed in the route sampling.

### Viewer Browser Flow

- Viewer login through the visible login form succeeded after the temporary viewer account was re-enabled.
- Viewer menu was reduced to read-only areas.
- Forced access to restricted routes redirected to `/403` with a clear Chinese no-permission message:
  - `/review`
  - `/workorder/create`
  - `/media`
  - `/model-service`
  - `/system/users`

### Usability Observations

- Users do not need to type internal UUIDs for the normal route-level workflow. IDs appear as technical trace/detail fields and URLs, which is acceptable for this stage.
- The first-version scope is clear on the login page and dashboard.
- Minor English/technical labels remain, such as `SCREEN / DASHBOARD`, API route fragments, `trace_id`, model provider keys, and enum-like fault names. These are acceptable for technical users but should be softened further for nontechnical demonstration if time allows.
- Recent demo lists still expose old `Task18I_` and `Task20C_` records. This is useful evidence for testing but visually rough for public demo recording.

## 4. API Workflow Trial Summary

A full `Task20C_20260629191147` flow was executed through authenticated API calls to simulate admin, expert, engineer, and viewer behavior. Result summary:

- Total checks: 78
- Passed: 75
- Blocked: 3
- Partial: 0
- Failed: 0
- Skipped: 0

Blocked items were expected external capabilities:

- OCR engine status: `disabled`
- `cloud_openai`: disabled, rule-based fallback verified
- `local_llama_cpp`: disabled, rule-based fallback verified

## 5. User Role Trial

| Role / user viewpoint | Status | Experience judgment |
| --- | --- | --- |
| Admin | usable | Login, dashboard, system status, model gateway, review, user management, and all main pages are reachable. Good for demo control. |
| Expert | usable | Contribution approval and conversion to knowledge are meaningful and reflect real expert governance. The flow is easiest to explain with prepared data. |
| Engineer | usable | Device, media, knowledge contribution, retrieval, diagnosis, SOP, task execution, and record tracing form a practical field workflow. |
| Viewer | usable | Read-only navigation is clear; restricted routes show a Chinese 403 explanation. |
| New maintainer | usable with guidance | Retrieval, SOP, diagnosis, and record center help onboarding, but the user still needs explanation of confidence, references, and blocked model/OCR states. |
| Judge / teacher | usable | The demo tells a coherent story if run along the recommended path and if blocked capabilities are not exaggerated. |

## 6. Business Flow Trial

| Flow | Status | Trial notes |
| --- | --- | --- |
| Dashboard | usable | Shows counts, topology illustration, recent tasks, and PV inverter positioning. Good first screen. |
| Devices | usable | Created `Task20C_` device, viewed detail, listed it, and verified viewer write denial. Device detail and maintenance history avoid manual UUID input in normal use. |
| Knowledge documents | usable | Contribution conversion produced an approved parsed document and one chunk; document detail and chunks were readable. |
| Knowledge contributions | usable | Engineer created/submitted experience; engineer review was blocked; expert approved and converted. Strong product value for experience capture. |
| Retrieval | usable | Query returned `trace_id`, 4 real references, retrieved chunks, and QA record persistence. Answer is credible when references exist. |
| Diagnosis | usable | Diagnosis returned trace, safety notes, record detail, and KG context. It supports field work but should remain "auxiliary diagnosis". |
| SOP | usable | Template creation, SOP generation, execution creation, and completion passed. It is demo-ready; export/signoff can be future work. |
| Tasks | usable | Task create, assign, start, complete, detail, and maintenance-record linkage passed. |
| Record center | usable | Overview, global search, QA detail, and device timeline passed. It is a practical audit entrance. |
| Media | usable | PNG upload, list, detail, authenticated preview, and media association passed. |
| OCR | blocked | OCR status endpoint is clear, but real recognition is disabled. It should not be demonstrated as completed OCR. |
| Knowledge graph | usable with boundary | Overview, graph, business context, search, and viewer write denial passed. Visualization is enough for demo but not a full graph analysis workspace. |
| Model gateway | partial | Rule-based provider works and fallback is useful. Cloud/local providers are disabled and should be explained as configurable external integrations. |
| System status | usable | Shows real database status and useful counts. Good for acceptance demonstration. |

## 7. Usability Scores

Score scale:

- 5 = 非常好，可直接演示
- 4 = 可用，有轻微体验问题
- 3 = 基本可用，但需要解释
- 2 = 功能存在但体验较差
- 1 = 不建议演示
- 0 = 不可用

| Module | Score | Comment |
| --- | ---: | --- |
| Login | 5 | Clear first-version scope and successful form login. |
| Dashboard | 4 | Strong positioning and useful counts; test-data names make it slightly rough. |
| Device inventory | 4 | Device list/detail/maintenance history work; final demo should use clean names. |
| Knowledge documents | 4 | Upload/parse/chunk concept is clear; approval/retrieval boundary needs explanation. |
| Knowledge contributions | 5 | Strongest business story: field experience to approved knowledge. |
| Retrieval QA | 4 | Real references and traceability are strong; no cloud model should be expected. |
| Fault diagnosis | 4 | Practical structured output and safety notes; still needs expert framing. |
| SOP | 4 | Complete enough for demo; export/print/signature would improve field use. |
| Maintenance tasks | 4 | Lifecycle is usable and traceable; task UI could be smoother for field teams. |
| Record center | 4 | Strong audit value; old test records and encoded text should be cleaned for public recording. |
| Media evidence | 4 | Upload/preview/association work; image understanding should not be implied. |
| OCR status | 2 | Status is clear, but real recognition is disabled. Only show as boundary/config item. |
| Knowledge graph | 4 | Business context and evidence are useful; visual canvas is still basic. |
| Model service | 3 | Useful for admin and extensibility, but ordinary users may misunderstand disabled providers. |
| System status | 5 | Clear database online signal and system counts. |
| Permission control | 5 | Viewer restriction and 403 messages are clear. |
| Overall UI | 4 | Chinese-first and coherent; remaining technical labels and test data need polish. |

## 8. Currently Unusable or Blocked

| Capability | Status | User impact |
| --- | --- | --- |
| Cloud model | blocked | `cloud_openai` is disabled; do not claim real online model generation. |
| Local llama.cpp | blocked | `local_llama_cpp` is disabled; do not claim real local GGUF inference. |
| OCR | blocked | `OCR_ENABLED=false`; do not claim image text recognition or image fault understanding. |
| LoongArch/Kylin | blocked | No real target-machine acceptance in this trial. |
| PostgreSQL Windows service | partial / blocked | Current native PostgreSQL process works, but Windows service persistence is not proven. |
| Public-demo data quality | partial | Test records are valuable for acceptance evidence but visually rough for final demo. |

## 9. User Needs Satisfaction

### Satisfied

- A user can log in and understand the product scope.
- Admin can supervise system status and manage users.
- Engineer can follow the main maintenance workflow.
- Expert can review and convert field knowledge.
- Viewer has read-only access and receives clear permission blocking.
- Retrieval, diagnosis, SOP, task, record center, media, and KG are connected enough for a convincing demo.

### Partially Satisfied

- New users can use the system, but they still need explanation of trace IDs, references, KG context, and model/OCR blocked states.
- Field engineers can use the web workflow, but mobile/offline ergonomics are not yet optimized.
- Media evidence is usable, but OCR/image understanding is not available.
- Model gateway is useful for administrators, but not ready as a user-facing AI selling point.

### Not Satisfied

- Real OCR recognition.
- Real cloud model generation.
- Real local llama.cpp inference.
- Real LoongArch/Kylin deployment acceptance.
- Reboot-stable Windows PostgreSQL service acceptance.

## 10. User Pain Points

- Public demo lists can show old acceptance markers such as `Task18I_` and `Task20C_`, which makes the product feel less polished.
- Some record-center text from old data appears with encoding artifacts. This should be cleaned before recording.
- Knowledge graph page is useful but still feels more like a lightweight evidence graph than a mature graph workspace.
- Model gateway page can confuse nontechnical users unless the presenter explicitly explains provider status and fallback.
- OCR status is honest but not useful to field users until real recognition is configured.

## 11. Recommended Future Development

### P0 - impacts real use

1. Run and pass LoongArch/Kylin target-machine deployment acceptance.
2. Fix or document PostgreSQL Windows service persistence for reboot-stable demos.
3. Prepare clean final demo data and hide/archive old verification records from demo views.
4. Configure and pass at least one real model provider if the demo wants to emphasize AI generation.
5. Improve error/blocked explanations for ordinary users on model/OCR pages.

### P1 - improves product experience

1. Better knowledge graph visual canvas and path explanation.
2. Task/SOP/diagnosis report export.
3. SOP PDF or work-ticket export.
4. Maintenance record reporting.
5. Message notifications for review/task assignment.
6. User operation log page.
7. Batch device import.
8. Better full-text search and filters.

### P2 - long-term enhancements

1. Mobile field workflow.
2. Multi-site/station management.
3. Spare-parts inventory.
4. Inspection scheduling.
5. Model output to knowledge contribution.
6. Vector retrieval after first-version delivery.
7. Image understanding after OCR/media workflow matures.
8. Multi-model evaluation and provider comparison.

## 12. Test Data Cleanup

Created with marker `Task20C_20260629191147`:

- Device: `15c7d2e0-c4bb-4feb-84c3-6a3d8d3fd176`
- Media: `b9938d1c-c40f-467c-be78-f8f87ff965b1`
- Contribution: `41e18bd5-40b3-433f-82ab-4d386775d5e9`
- Converted document: `bb5317d0-6e99-4a77-af4a-f7ce78228e2e`
- QA trace: `qa_20260629111150_0f8e1b248b`
- Diagnosis trace: `diag_20260629111150_4050271fe1`
- SOP template: `ec8540aa-23cb-449f-94dc-ffb35f0b030d`
- SOP execution: `c2536611-c844-4734-907d-7cf6277cd142`
- Maintenance task: `9683e664-62ef-4c4b-a40c-c625ef075156`
- Correction: `5db58435-f68e-4081-b520-c95d716a3b01`

Cleanup performed:

- SOP template archived.
- Converted document archived.
- Device retired.
- `Task20C_engineer`, `Task20C_expert`, and `Task20C_viewer` disabled.

Retained for audit/traceability:

- QA record.
- Diagnosis record.
- Completed task.
- Maintenance records.
- SOP execution record.
- Media record and uploaded file.
- Converted contribution record.
- Correction record.

Retention reason: these are audit/trace records created by the workflow. They were not hard-deleted to avoid violating traceability and data deletion constraints.

## 13. Final User Acceptance Judgment

- Ready for demo: yes, with clean demo data and a guided demo path.
- Ready for real internal trial: yes, for knowledge retrieval, diagnosis assistance, SOP, task, records, and role-based review.
- Ready for full production: partial / blocked.
- Conditions for full production:
  - real LoongArch/Kylin deployment acceptance;
  - stable PostgreSQL service operation;
  - clean demo/production data separation;
  - real model/OCR configuration if those capabilities are included in the delivery claim;
  - further field-use polish for mobile, exports, and notifications.

## 14. Commands and Evidence

| Evidence | Result |
| --- | --- |
| `git status --short` | clean at start of the trial after Task 20B commit |
| `GET http://127.0.0.1:8000/api/health` | failed: no server was reachable on 8000 |
| `scripts/start_all_windows.ps1 -BackendPort 8000 -SkipPostgreSQL` | failed to open 8000; no migration was executed |
| `GET http://127.0.0.1:8010/api/health` | passed |
| `GET http://127.0.0.1:8010/api/system/status` | passed, database online |
| Browser login as admin | passed |
| Browser core route sampling | passed, no blank page or console error observed |
| Browser login as viewer | passed |
| Browser forced restricted-route checks | passed, redirected to `/403` with Chinese no-permission message |
| In-memory `Task20C_` workflow API trial | passed, 78 total / 75 passed / 3 blocked / 0 failed |
| Test data soft cleanup | passed with retained audit records |

## 15. Conclusion

From a real user perspective, Energy-Maintenance is usable as a first-version PV inverter maintenance workbench. The strongest demo story is:

```text
device inventory -> field media/evidence -> frontline knowledge contribution -> expert review -> knowledge document/chunk -> retrieval with references -> diagnosis -> SOP -> maintenance task -> record center -> knowledge graph evidence
```

The project should proceed to final demo material preparation after cleaning demo data. It should not be described as fully production-ready until external model/OCR/hardware/service blockers are resolved and retested.
