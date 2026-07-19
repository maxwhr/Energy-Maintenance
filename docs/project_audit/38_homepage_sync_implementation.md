# Task 29A Homepage Sync Implementation

## Reference and Method

- Reference repository: `maxwhr/Energy-Maintenance`
- Reference commit: `16815c4886af1e8f92f69a7a19f4a725d67d5904`
- Integration method: read-only extraction, file-by-file comparison, and manual adaptation
- Explicitly not used: checkout, merge, cherry-pick, pull, restore, or whole-tree replacement

The reference commit was used only for public-page visual language and structure. Current backend contracts, RAG behavior, typed API clients, stores, permission guards, and business pages remain authoritative.

## Migrated Public Structure

`frontend/src/views/Login.vue` now provides:

- fixed industrial navigation with responsive collapsed menu;
- full-bleed solar-field hero and clear entry actions;
- Huawei SUN2000 support-scope section;
- three image-led, sticky narrative capability sections;
- six-item interactive capability orbit with keyboard and focus states;
- eight-step standardized maintenance workflow;
- conservative LoongArch and Kylin deployment positioning;
- four-role account guide and footer;
- `IntersectionObserver` reveal effects with cleanup;
- `prefers-reduced-motion` behavior;
- lazy loading for non-hero inline images.

`frontend/src/views/AuthLogin.vue` is a dedicated authentication page. It reuses the current `loginApi`, `useUserStore`, token/user response, route guard, and redirect query. It shows client or backend errors inline and does not print passwords or full responses.

`frontend/src/views/Register.vue` is an account and role explanation page, not a self-registration form. It states that administrators create accounts and links to `/auth/login`.

## Files Changed for Task 29A

- `frontend/src/views/Login.vue`
- `frontend/src/views/AuthLogin.vue` (new)
- `frontend/src/views/Register.vue`
- `frontend/src/router/index.ts` (minimal `/auth/login` and `/assistant` compatibility declarations plus logged-in public-entry redirect)
- `frontend/src/assets/auth/access-denied.png` (new)
- `frontend/src/assets/auth/dual-inverter.png` (new)
- `frontend/src/assets/auth/fault-diagnosis.png` (new)
- `frontend/src/assets/auth/field-engineer.png` (new)
- `frontend/src/assets/auth/knowledge-search.png` (new)
- `frontend/src/assets/auth/solar-field.png` (new)
- `docs/project_audit/37_homepage_sync_checkpoint.md`
- `docs/project_audit/38_homepage_sync_implementation.md`
- `docs/project_audit/39_homepage_visual_acceptance.md`
- `docs/project_audit/task29a_homepage_acceptance.json`

`frontend/src/styles/global.css` was inspected but not modified. The router already contained unrelated working-tree changes before this task; only the public route compatibility listed above belongs to Task 29A.

## Original Image Inventory

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `access-denied.png` | 4,479,056 | `7eb800b514a01cdd6371d52ab794c87cfb571fb4463232b0f799ae4066b34901` |
| `dual-inverter.png` | 3,981,713 | `293776224d68f4b0d813402f93868a16cc195dfde87abe04dca14a3882c8e01e` |
| `fault-diagnosis.png` | 4,487,152 | `4c938cf7b5663f1f3b04b742d0de0f259d3cc39fc6b09fe39c9ad5dbb682c1eb` |
| `field-engineer.png` | 4,929,674 | `63705b4ea8e3206beb19a976d804eae84ba6adca1e02286cfa43707b120d917a` |
| `knowledge-search.png` | 4,440,847 | `7d1b936e83a2abfe0888d7d2e04e3f8e49b8723deda505bbfd919babcdfc0541` |
| `solar-field.png` | 7,396,475 | `2377c6f04226cf253bf167e33d75e0bbededed5c3bcb9074d7ccec91807f23ad` |

Five assets are referenced by the current homepage. `dual-inverter.png` is retained as an original reference asset but intentionally not rendered, avoiding a dual-manufacturer production claim.

## Route and Authentication Compatibility

- `/login`: public product introduction
- `/auth/login`: public account/password login
- `/register`: public account and permission explanation
- `/assistant`: alias for the existing assistant page
- successful login: honors a safe local `redirect` query, otherwise routes to `/dashboard`
- authenticated access to `/login` or `/auth/login`: routes to `/dashboard`
- unauthenticated business access: current guard returns to `/login` with the intended redirect query
- `/403`: unchanged

No API URL, token field, user-store contract, dashboard route, or permission model was replaced.

## Copy and Product Scope

The public copy now describes the verified production scope as Huawei SUN2000 PV inverter maintenance. It presents real text retrieval, source tracing, assisted diagnosis, SOP, task workflow, knowledge review, human correction, and traceability without claiming unverified real-time OCR, online vision, hybrid retrieval, or real-machine LoongArch acceptance.

The system architecture remains extensible to additional inverter manufacturers. Per the user's clarification, the reference field-engineer image that may show Sungrow equipment is retained for future expansion, while the surrounding copy does not state that Sungrow production support is currently online.

## Content Not Migrated

No content from the reference commit was copied into:

- `frontend/src/api/retrieval.ts`
- `frontend/src/views/knowledge/Search.vue`
- `frontend/src/views/assistant/Chat.vue`
- `frontend/src/views/device/Alarms.vue`
- `frontend/src/views/device/Models.vue`
- `frontend/src/views/diagnosis/index.vue`
- `backend/app/`
- database models, migrations, configuration, providers, storage, or knowledge data

## Known Limitations

- Original PNGs are 3.98 MB to 7.40 MB each. They were intentionally preserved without recompression as required; non-hero images use lazy loading.
- Reference images contain small generation marks inherited from the source assets.
- `field-engineer.png` can visually suggest Sungrow equipment. This is an explicitly accepted future-expansion visual, not a formal capability statement.
