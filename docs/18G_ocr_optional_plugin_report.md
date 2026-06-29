# Task 18G OCR Optional Plugin Report

## Scope

Task 18G adds an optional OCR workflow for uploaded image media evidence. The first-version Energy-Maintenance core remains Huawei/Sungrow PV inverter maintenance, PostgreSQL-backed retrieval, diagnosis, tasks, records, and source tracing.

OCR is not a required first-version dependency. It is disabled by default and must not be described as image fault recognition.

## Configuration

```env
OCR_ENABLED=false
OCR_PROVIDER=tesseract
OCR_LANG=chi_sim+eng
OCR_TIMEOUT_SECONDS=30
OCR_MAX_IMAGE_MB=10
OCR_TESSERACT_CMD=tesseract
```

## Implementation Summary

- Backend adapter: Tesseract command-line invocation through `subprocess`.
- Backend service: OCR status, media OCR trigger, media OCR readback, safe disabled/not-configured handling.
- Media API: `GET /api/media/ocr/status`, `POST /api/media/{media_id}/ocr`, `GET /api/media/{media_id}/ocr`.
- Retrieval and diagnosis: `use_ocr_text=false` by default; processed OCR text can be included only when explicitly requested.
- Record tracing: related media payloads expose OCR status, provider, language, processed time, error summary, and OCR text summary from existing fields.
- Frontend: media page, media evidence components, retrieval page, diagnosis page, and trace page show OCR status or optional OCR context without treating OCR as approved knowledge.

## Safety Boundaries

- OCR extracts text from image files only.
- OCR is not image understanding, visual fault recognition, or a substitute for engineer judgement.
- OCR results are machine-recognized reference text and may contain errors.
- OCR text does not become approved knowledge automatically.
- Retrieval references still come from real approved `knowledge_chunks`.
- No Alembic migration was added.
- `alembic upgrade head` was not executed.
- No Docker, SQLite, PaddleOCR, RapidOCR, pgvector, embedding, or deep-learning OCR dependency was introduced.

## Verification Result

| Check | Result | Notes |
| --- | --- | --- |
| Backend compile | passed | `uv run python -m compileall app scripts` passed. |
| Alembic current | passed | Current revision is `20260601_0003 (head)`. |
| Frontend install/build | passed | `npm.cmd install` and `npm.cmd run build` passed. |
| Static frontend install | passed | `backend/scripts/build_and_install_frontend.ps1` passed. |
| Final smoke | passed | `scripts/final_smoke_test.ps1` passed, 23 total and 0 failed. |
| OCR flow | blocked | OCR status is `disabled` because `OCR_ENABLED=false`. |
| Tesseract environment | blocked | `tesseract` was not found in `PATH`; status is `not_configured`. |

## Current Mode

```text
mode=blocked
reason=OCR_ENABLED=false and Tesseract is not configured on this Windows host
```

This is an acceptable Task 18G result. It confirms the optional OCR path is wired safely without claiming real OCR recognition.

## Future Activation Steps

Only after the user decides to enable OCR on a target machine:

1. Install a native Tesseract package appropriate for the host OS and CPU architecture.
2. Install required language data such as `chi_sim` and `eng`.
3. Set `OCR_ENABLED=true` in local `backend/.env`.
4. Run `scripts/check_tesseract_env.ps1` on Windows or `scripts/check_tesseract_env.sh` on LoongArch/Kylin.
5. Run `cd backend && uv run python scripts/check_ocr_flow.py`.

Do not commit local OCR binaries, tessdata, `.env`, or generated OCR logs.
