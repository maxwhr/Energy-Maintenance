# Task 29A Homepage Visual Acceptance

## Result

Final status: `READY`

The public homepage sync, dedicated login flow, account guide, responsive layouts, image delivery, and protected-business regression checks passed. Evidence is under `.runtime/task29a/` and is not a production build artifact.

## Responsive Visual Matrix

| Class | Viewports | Result |
| --- | --- | --- |
| Desktop | 1920x1080, 1440x900, 1366x768 | passed |
| Tablet | 1024x768, 768x1024 | passed |
| Mobile | 390x844 | passed |

All six viewports had document width equal to viewport width. No horizontal overflow, clipped login card, blocked sticky section, orbit overflow, or blank hero was detected. Sixteen screenshots were captured under `.runtime/task29a/browser/screenshots/` and visually inspected.

## Navigation and Interaction

- Desktop anchors `核心能力`, `检修流程`, `支持范围`, and `账号说明`: passed
- Anchor targets remained 68 px to 106.23 px below the fixed navigation: passed
- Tablet/mobile collapsed menu opens, displays, navigates, and closes: passed
- Mobile anchor targets remained 84.08 px to 97.25 px below the fixed navigation: passed
- Six capability controls update the detail panel without navigation or network calls: passed
- Capability keyboard/focus semantics and selected `aria-pressed` state: passed

The original fixed-delay browser assertion was replaced with a condition that waits until smooth scrolling settles at the target. This corrected a test-timing false negative without changing homepage behavior.

## Image Acceptance

- Six extracted PNG files exist and match recorded SHA-256 values: passed
- Homepage-loaded source images: five
- Inline images completed with non-zero natural dimensions: four of four
- Hero background loaded through the Vite resource graph: passed
- Image 404 count: `0`
- Remote image URLs: none
- Base64-embedded large images: none

`dual-inverter.png` is preserved but not rendered. The user approved retaining `field-engineer.png` for the future Sungrow expansion path; current formal copy remains Huawei SUN2000.

## Login and Route Acceptance

- `/login` public homepage: passed
- `/auth/login` desktop and mobile layout: passed
- `/register` account explanation with four roles and no registration form: passed
- empty-account validation: passed
- invalid-login backend error display: passed
- password absent from rendered error text: passed
- real administrator login: passed
- token and user persistence: passed
- safe redirect query to `/knowledge/search`: passed
- authenticated `/login` redirect to `/dashboard`: passed
- unauthenticated business-route guard: passed
- `/assistant`, `/diagnosis`, `/sop`, `/maintenance-workflow`, `/trace`: nonblank and accessible after login
- `/403`: unchanged and accessible

The real login check used the existing local account and current backend contract. No database schema, migration, or business data was changed; normal authentication may update the account's conventional `last_login` timestamp.

## Accessibility and Motion

- meaningful inline-image alt text: passed
- menu and capability button labels: passed
- visible focus treatment: passed
- `prefers-reduced-motion` query matched in reduced-motion context: passed
- reveal content remains visible: passed
- continuous animation disabled: passed
- smooth-scroll/reveal transition effectively disabled: passed

## Static and Build Verification

| Check | Command or Evidence | Result |
| --- | --- | --- |
| Vue type check | `npm.cmd exec vue-tsc -- --noEmit` | passed |
| Isolated Vite build | `npm.cmd exec vite -- build --outDir ..\.runtime\task29a\frontend-build --emptyOutDir` | passed |
| Modules transformed | Vite output | 1,986 |
| Formal build directories overwritten | command/output inspection | no |
| Browser request failures | Playwright/CDP report | 0 |
| Blocking console errors | Playwright/CDP report | 0 |
| Image 404s | Playwright/CDP report | 0 |
| Protected hashes | `.runtime/task29a/capture_baseline.py verify` | passed |
| Prohibited homepage claims | targeted `rg` scan | none |

The isolated build completed with Vite 8.0.16. Output was written only to `.runtime/task29a/frontend-build`; `frontend/dist` and `backend/static/frontend` were not used as build targets.

The temporary Vite server on 5178, FastAPI server on 8010, and native PostgreSQL instance on 5432 that were started only for this acceptance run were stopped afterward. No listener remained on those three ports.

## Protected Business Regression

Hash verification confirms no Task 29A change in the six protected RAG/business files or in the 325-file `backend/app` tree. No database, migration, provider, environment, knowledge asset, upload, or storage modification was performed.

## Remaining Non-blocking Issues

- Original full-resolution images increase initial/cache transfer size; conversion was explicitly deferred.
- Source image generation marks remain because original assets could not be edited.
- The approved field-engineer visual may be read as future Sungrow scope unless viewers also read the formal Huawei SUN2000 copy.

These issues do not block the Task 29A acceptance criteria.
