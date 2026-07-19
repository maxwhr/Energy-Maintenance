# Task 29B Login Runtime Bundle Repair

## Result

- Final status: `SELECTIVE_AUTH_SOURCE_RESTORED_AND_BUILT`
- Reference commit: `16815c4886af1e8f92f69a7a19f4a725d67d5904`
- Reference commit available locally: yes
- Git pull / merge / rebase / cherry-pick: not executed
- Database connection or migration: not executed
- Backend business and RAG protected paths: unchanged

## Report Number

The requested report number 58 was already occupied by
`58_keyword_score_provenance_and_fusion_localization.md`. This report therefore
uses the next available number, 61, without overwriting an existing audit.

## Initial Runtime Observation

At task start, port 8000 had no listener. Therefore the old centered account
card reported by the user could not be reproduced from an active process, and
there was no original PID or working directory to terminate or attribute.

For pre-change HTTP evidence, the task started a temporary FastAPI/Uvicorn
instance from `D:\Work Space\Energy-Maintenance\backend`. The pre-change served
bundle was already classified as `NEW_BUNDLE_CONFIRMED`:

- pre-change static index SHA-256:
  `62fa7fc5635d93be5b2b8dc4490c73cfcec3efdecde9bedeb3efd5867ce2f874`
- pre-change Login chunk:
  `Login-CpB3L2fq.js`
- pre-change Login chunk SHA-256:
  `97aa272e22ac5b79b9c8723ddbb9b9c9502128d82b010c213f3f73d49d9832be`
- old account markers: 0
- new page markers: present

The user-reported old bundle is therefore historical and not attributable to
the task-start runtime. It is not classified as a browser-cache or service
worker fault without evidence.

## Source and Reference Comparison

The local source was partially newer than the reference commit:

- `/login` already mapped to `frontend/src/views/Login.vue`.
- `/auth/login` already mapped to `frontend/src/views/AuthLogin.vue`.
- `AuthLogin.vue` already preserved `loginApi`, `useUserStore`, token storage,
  safe redirect handling, error handling, and password visibility control.
- `Register.vue` already displayed account-application guidance and did not
  expose self-service registration.
- `Login.vue` was a public homepage but did not contain the requested headline
  and did not use `dual-inverter.png`.

Root-cause classification: `SOURCE_NOT_UPDATED` for the two missing public-home
visual requirements. No evidence supports `BROWSER_CACHE_STALE` or
`SERVICE_WORKER_CACHE_STALE`.

## Selective Repair

Only `frontend/src/views/Login.vue` source was selectively changed:

1. Restored the headline `让每一次检修 / 都有据可循`.
2. Restored the CTA `进入检修工作台`.
3. Added the supporting phrase `从知识进入现场`.
4. Renamed the public navigation label to `检修闭环`.
5. Replaced the incorrect `access-denied.png` scene reference with the existing
   `dual-inverter.png` asset.

`AuthLogin.vue`, `Register.vue`, router logic, API clients, store logic, RBAC,
backend Python code, retrieval code, fixtures, and database configuration were
not changed by this task.

No images were copied from Git because every required image already existed
locally and decoded successfully.

## Static Serving Map

- source frontend: `D:\Work Space\Energy-Maintenance\frontend`
- build output: `D:\Work Space\Energy-Maintenance\frontend\dist`
- served static directory:
  `D:\Work Space\Energy-Maintenance\backend\static\frontend`
- served index:
  `D:\Work Space\Energy-Maintenance\backend\static\frontend\index.html`
- SPA fallback: `backend/app/core/static_frontend.py`
- deployment script: `backend/scripts/build_and_install_frontend.ps1`
- copy step required: yes

The pre-deployment static directory was copied to
`.runtime/task29b/static_backup/before_deploy` with a file and SHA-256 manifest.

## Build and Deployment

- explicit `vue-tsc -b`: passed
- `npm.cmd run build`: passed
- Vite transformed 1,986 modules
- existing install script: passed
- copied static files: 77
- package lock SHA-256 unchanged:
  `87fd618a989f4787871e1a6bf33268330d90873997e90f10b88e39bab5ae0d4e`
- final static index SHA-256:
  `0577e49e43952675a8d88ac8c20e2c2a1c775204a5eed20040518b5497e848e3`
- final Login chunk: `Login-BJ78ho0w.js`
- final Login chunk SHA-256:
  `a58b964019161ec34aa2e1c536c99197c3f381b3cd07845cd02fea2a7524bba9`
- final AuthLogin chunk: `AuthLogin-nMw6dkOm.js`
- final bundle identity: `NEW_BUNDLE_CONFIRMED`
- old account markers in final JavaScript: 0
- service worker files: 0

## Route and Image Acceptance

No-cache HTTP requests returned 200 for:

- `/login`
- `/auth/login`
- `/register`

The five required built assets returned HTTP 200 and `image/png`:

- `solar-field-CGgQTDkn.png`
- `dual-inverter-DqgnDYsy.png`
- `knowledge-search-BJaJ1azS.png`
- `fault-diagnosis-C2rwSg4b.png`
- `field-engineer-Cn-aPCFH.png`

After scrolling through the real DOM page, all four content images reported a
non-zero natural width and height. No missing or case-mismatched asset path was
found.

## Browser Acceptance

Desktop and 390 x 844 mobile browser checks passed for the visual routes:

- `/login` displayed the public homepage, required headline, CTA, navigation,
  capability content, workflow content, and no old account card.
- `/auth/login` displayed the photovoltaic background, introduction, identity
  card, username and password inputs, CTA, and return link.
- `/register` displayed account-application guidance and explicitly disabled
  self-service registration.
- mobile pages had no horizontal overflow.
- browser console errors: 0
- browser console warnings: 0
- static page API failures: 0
- Cache Storage keys: 0
- localStorage keys on the fresh public page: 0

The empty-form validation displayed `请输入账号`. A real credential login,
wrong-password server response, token restoration, and dashboard redirect were
not executed because this task explicitly prohibited connecting to the formal
database. The current `loginApi`, store update, safe redirect, and catch-path
logic were preserved and verified in source/build output; they are not reported
as a real backend authentication pass.

Screenshots:

- `.runtime/task29b/screenshots/login_new_desktop.png`
- `.runtime/task29b/screenshots/login_new_mobile.png`
- `.runtime/task29b/screenshots/auth_login_desktop.png`
- `.runtime/task29b/screenshots/auth_login_mobile.png`

## Multiple Frontend Roots

`delivery_staging/frontend` also contains a historical `Login.vue`, but the
active Vite configuration and install script use the root `frontend` directory.
No alternate frontend root was deleted or modified.

## RAG Protection

Before-and-after aggregate SHA-256 values match for:

- `backend/app/services/`
- `backend/app/repositories/`
- `backend/app/models/`
- `backend/alembic/`
- Task 27A v1 fixture
- Task 27A v2 fixture

No RAG migration, database operation, provider call, vector operation, remote
Git access, Git history rewrite, or unrelated process termination occurred.

## Final Runtime

- URL: `http://127.0.0.1:8000/login`
- server: FastAPI/Uvicorn
- listener PID: 40372
- working directory: `D:\Work Space\Energy-Maintenance\backend`
- process was started by Task 29B: yes

## Remaining Boundary

The visual and static-bundle repair is complete. Real credential success and
wrong-password backend behavior remain intentionally unexecuted under the
no-database boundary and require a separately approved authentication smoke test
against a non-production or explicitly authorized database.
