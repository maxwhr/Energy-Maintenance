# Task 30A Real Provider Preflight

## Decision

- Approval token: validated in process; token value is not persisted in this report.
- Test database: `energy_maintenance_task30a_test` on `127.0.0.1:55433`.
- Clone source: `energy_maintenance_task28a_r3i_test`.
- Alembic: `20260712_0015 (head)`.
- Production database connection: not used.
- Windows service `postgresql-x64-16`: kept stopped and disabled.

## Provider Configuration

| Purpose | Provider type | Provider code | Model | Endpoint host | Configured | Secret present |
| --- | --- | --- | --- | --- | --- | --- |
| OCR | OpenAI-compatible OCR | `custom_ocr_api` | `step-3.7-flash` | `api.stepfun.com` | yes | yes |
| Vision | Multimodal vision | `mimo_2_5` | `step-3.7-flash` | `api.stepfun.com` | yes | yes |

Only presence was checked. No credential, credential length, Authorization header, or complete request/response is recorded.

## Safety Gates

- `TASK30A_ALLOW_REAL_PROVIDER=true`: validated.
- `TASK30A_ALLOW_TEST_DB_WRITES=true`: validated.
- `TASK30A_MAX_REAL_PROVIDER_CALLS=16`: validated.
- Database identity and port are checked before test writes and before call-budget acquisition.
- Call attempts are counted from `external_api_call_logs` under a PostgreSQL advisory lock.
- The seventeenth attempt is blocked locally; unit test passed.
- Cloud LLM, local LLM, embedding, vector search, and DashVector were disabled for the test process.

## Image Privacy Preflight

Four test-only PNG files passed decode, MIME, SHA-256, dimension, EXIF removal, GPS, and privacy checks. No face, address, phone, email, customer name, real serial number, or precise location was present. Privacy rejection count was zero.

Source evidence: `.runtime/task30a/input/image_manifest.json` and `.runtime/task30a/provider_calls/provider_preflight.json`.
