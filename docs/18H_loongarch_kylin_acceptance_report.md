# Task 18H LoongArch / Kylin Acceptance Report

## Scope

Task 18H freezes the Energy-Maintenance first-version delivery state and prepares real LoongArch + Kylin deployment acceptance.

This task does not add business features, does not create Alembic migrations, does not introduce Docker, SQLite, pgvector, embedding, external graph databases, model binaries, or OCR binaries.

## Windows Final Regression

| Item | Result | Notes |
| --- | --- | --- |
| Git pre-check | passed | Only `prompt.txt`, `scripts/final_smoke_test.sh`, and `frontend/package-lock.json` were present before final docs/package work; `prompt.txt` is intentionally untracked. |
| Backend compileall | passed | `uv run python -m compileall app scripts` passed. |
| Alembic current | passed | `20260601_0003 (head)`. |
| PostgreSQL API status | passed | `/api/system/status` returned `database_status=online`. |
| PostgreSQL service | admin-required | Windows service `postgresql-x64-16` is `Stopped / Disabled`; standalone `postgres.exe` is running and serving the local validation database. |
| Frontend install | passed | `npm.cmd install` completed. |
| npm audit | passed | Initial `form-data` high severity advisory was fixed with `npm.cmd audit fix`; rerun reported `found 0 vulnerabilities`. |
| Frontend build | passed | `npm.cmd run build` passed. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` installed 56 files to `backend/static/frontend`. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| KG flow | passed | `check_knowledge_graph_flow.py` passed and viewer approval was blocked. |
| KG business integration | passed | `check_kg_business_integration.py` passed for retrieval, diagnosis, SOP, and viewer read-only checks. |
| Cloud model | blocked | Cloud credentials are missing; rule-based fallback and secret safety were verified. |
| Local llama.cpp | blocked | Local llama.cpp is disabled; fallback and path/header safety were verified. |
| OCR | blocked | OCR is disabled and Tesseract is not configured; blocked mode was verified. |

## LoongArch / Kylin Acceptance

| Item | Result | Notes |
| --- | --- | --- |
| Target available | blocked | No target LoongArch/Kylin host was available from this Windows session. |
| `uname -m` | not executed | Must be captured on target host. |
| `/etc/os-release` | not executed | Must be captured on target host. |
| PostgreSQL | not executed | Must be installed/started on target host. |
| Python / Node / npm | not executed | Must be verified on target host. |
| Alembic upgrade | not executed | Allowed only on the target database during deployment initialization. |
| Backend startup | not executed | Must be verified on target host. |
| Linux smoke | blocked | `scripts/final_smoke_test.sh` is ready, but this Windows host only has unavailable WSL `bash`. |

Current result:

```text
LoongArch/Kylin acceptance = blocked
```

This is not a failure of the code package; it means real target hardware or VM validation still has to be performed.

## Delivery Package Strategy

The delivery package should be created from committed repository contents.

Included:

- `backend/`
- `frontend/`
- `docs/`
- `scripts/`
- `README.md`
- `backend/README.md`
- `AGENTS.md`
- Alembic migrations
- `backend/static/frontend` demonstration build
- package lock files

Excluded:

- `.env`
- API keys and local secrets
- `node_modules`
- `frontend/dist`
- local PostgreSQL data
- uploaded runtime files
- logs and caches
- GGUF/model files
- OCR binaries and tessdata
- `prompt.txt`
- local legacy frontend backup folders

## Target Deployment Steps

On the target host:

```bash
cd /path/to/Energy-Maintenance
bash scripts/check_loongarch_kylin.sh

cd backend
uv sync
uv run python -m alembic -c alembic.ini upgrade head
uv run python scripts/seed_final_demo_data.py
uv run python scripts/create_admin_user.py

cd ../frontend
npm install
npm run build

cd ../backend
bash scripts/build_and_install_frontend.sh
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Then:

```bash
cd /path/to/Energy-Maintenance
API_BASE_URL=http://127.0.0.1:8000 bash scripts/final_smoke_test.sh
```

## Final Freeze Status

- Windows final regression: passed.
- Delivery scripts/docs: ready.
- npm audit: passed after safe package-lock update.
- LoongArch/Kylin real-machine acceptance: blocked.
- PostgreSQL Windows service persistence: admin-required.
- Optional cloud/local/OCR capabilities: blocked unless explicitly configured and tested.

## Recommendation

Freeze business features. Proceed to final docs, PPT, and demo video script while scheduling a real LoongArch/Kylin deployment validation session.
