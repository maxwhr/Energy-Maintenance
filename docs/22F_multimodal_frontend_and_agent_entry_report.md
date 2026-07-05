# Task 22F: Multimodal Frontend and Agent Entry Report

## Scope

Task 22F adds a real frontend entry for the multimodal evidence center and agent workbench.

The page is focused on Huawei / Sungrow PV inverter maintenance evidence. It displays media evidence, OCR and AI analysis records, provider gateway status, evidence links, and agent run artifacts through real backend APIs.

This task does not call real mimo-2.5, cloud vision, local model, or OCR services. It does not add database migrations and does not generate delivery packages.

## Frontend Entry

New route:

- `/multimodal`

New menu entry:

- 多模态证据中心

The menu is placed near 媒体资料 so engineers can move from uploaded inverter field images to OCR / AI evidence review.

## Implemented UI

- External provider status panel.
- Provider check / dry-run / mock-run buttons with role controls.
- Media filtering and media selection.
- Processing job list.
- OCR dry-run, AI dry-run, AI mock-run, and OCR mock-run actions.
- OCR result display.
- AI multimodal analysis display and human review actions.
- Evidence link list and create form.
- Agent definitions and tool selection.
- Dry-run Agent Run creation.
- Agent steps, tool calls, artifacts, and approvals display.
- Viewer read-only behavior.

All main actions call backend APIs. The frontend does not fabricate success results.

## Backend APIs Used

- `GET /api/external-apis/status`
- `POST /api/external-apis/providers/{provider_code}/check`
- `POST /api/external-apis/dry-run`
- `POST /api/external-apis/mock-run`
- `GET /api/media`
- `GET /api/multimodal/media/{media_id}/summary`
- `GET /api/multimodal/media/{media_id}/jobs`
- `POST /api/multimodal/media/{media_id}/jobs`
- `GET /api/multimodal/media/{media_id}/ocr-results`
- `GET /api/multimodal/media/{media_id}/analyses`
- `POST /api/multimodal/analyses/{analysis_id}/review`
- `GET /api/multimodal/evidence-links`
- `POST /api/multimodal/evidence-links`
- `GET /api/agents/definitions`
- `GET /api/agents/tools`
- `POST /api/agents/runs`
- `GET /api/agents/runs/{run_id}`
- `GET /api/agents/runs/{run_id}/steps`
- `GET /api/agents/runs/{run_id}/tool-calls`
- `GET /api/agents/runs/{run_id}/artifacts`
- `GET /api/agents/runs/{run_id}/approvals`
- `GET /api/agents/events`

## Browser Acceptance

New script:

- `backend/scripts/check_task22f_multimodal_frontend_browser.mjs`

The script uses headless Chrome / Edge through CDP and validates:

- admin browser login;
- media image upload through the UI;
- `/multimodal` page rendering;
- provider check and dry-run;
- OCR dry-run and AI dry-run job persistence;
- OCR mock-run and AI mock-run result persistence;
- AI analysis review;
- evidence link creation;
- dry-run Agent Run creation;
- viewer read-only UI controls;
- no blocking browser runtime errors;
- no unexpected network failures;
- no delivery package generation.

## Boundaries

- Real external API calls remain disabled unless a future task supplies and validates provider credentials.
- OCR and AI results created by mock-run remain explicitly marked as mocked.
- Machine-recognition output is auxiliary evidence and requires human review.
- This task does not claim real image fault recognition.
- This task does not introduce OCR engine installation, model downloads, pgvector, embedding, Neo4j, Docker, or SQLite.

## Verification Commands

Recommended checks:

```powershell
cd "D:\Work Space\Energy-Maintenance\backend"
$env:DATABASE_URL="postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance"
uv run python -m compileall app scripts
uv run python -m alembic -c alembic.ini current
uv run python scripts\check_external_api_gateway_flow.py
uv run python scripts\check_multimodal_evidence_flow.py
uv run python scripts\check_multimodal_adapter_contract.py
uv run python scripts\check_agent_business_tools_flow.py
node .\scripts\check_task22f_multimodal_frontend_browser.mjs

cd "D:\Work Space\Energy-Maintenance\frontend"
npm.cmd install
npm.cmd audit
npm.cmd run build

cd "D:\Work Space\Energy-Maintenance\backend"
powershell -ExecutionPolicy Bypass -File .\scripts\build_and_install_frontend.ps1

cd "D:\Work Space\Energy-Maintenance"
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010
```

Do not create delivery packages during Task 22F.
## Task 22G Follow-up

The `/multimodal` frontend entry now creates a dedicated `multimodal_evidence_agent` orchestration run instead of only displaying generic agent runtime records.

The page displays:

- backend timeline;
- tool calls;
- multimodal evidence summary;
- safety checklist;
- artifact trace summary;
- blocked/dry-run/mocked labels;
- final answer with machine-evidence boundary.

The change keeps viewer read-only behavior and limits mock-run to expert/admin users.
