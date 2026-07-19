# Task 27A Production QA Write Incident

## Incident Status

`PENDING_AUTHORIZED_CLEANUP`

The record has been uniquely identified using a read-only query. Cleanup has not been authorized and has not been executed.

## Incident Facts

- Event time: `2026-07-16T17:19:57.919682+08:00`
- Triggering test: `backend/tests/integration/test_exact_query_fast_path.py`
- Trigger: the integration request omitted `persist_result=false`.
- Query: `SUN2000-100KTL-M1 通信参数`
- QA record ID: `4a9eeab8-91de-43bb-90ec-78a3d6bba7be`
- Trace ID: `qa_req_a92bd4d743373941ff949e900b972057`
- Request ID: `req_075409308b6f40c989324d382a3bb574`
- Created by: user `admin` (`6eb54846-0555-49fe-ba7a-fc8d53915868`)
- Provider/model: rule-based / `huawei_sun2000_query_aware_keyword_v1`
- References: 0
- Retrieved chunks: 0
- Detected sensitive keys: none
- Production QA count impact: 2597 to 2598

## Impact Assessment

The row contains a maintenance test query and a short rule-based answer. The read-only inspection found no API key, authorization value, password, secret, access token, reference payload, or retrieved chunk payload. It does not alter knowledge documents, chunks, scope eligibility, retrieval labels, or the frozen evaluation. It can, however, appear as an unwanted QA item in Record Center and means Task 27A cannot claim zero production writes across the whole task.

The final R2 evaluation and all completed R3 probes used a read-only transaction or `persist_result=false`; they did not create additional QA rows. The final R3 count remained 2598.

## Current Record State

The record remains present in `energy_maintenance`. No status/archive field exists on `qa_records`, so it is described operationally as retained pending an authorized exact cleanup. The unique read-only inspection found exactly one candidate for the exact query.

## Corrective Action Already Applied

`backend/tests/integration/test_exact_query_fast_path.py` now passes `persist_result=false`. Task 27A evaluation and API probes also set this flag explicitly. Database-guard tests refuse persistence checks when the database name lacks `_test` or `task27a`.

Additional controls added in R3:

- `inspect_task27a_production_qa_incident.py` performs read-only exact identification and emits only a sanitized summary.
- `cleanup_task27a_production_qa_incident.py` defaults to dry-run.
- Cleanup requires an exact connected database name, record ID, trace ID, request ID, exact query, `--apply`, and a named human authorizer.
- Cleanup refuses zero/multiple candidates, guard mismatches, or an unexpected post-delete count.
- The isolated test-database provisioner refuses formal/maintenance databases and unsafe database names.

## Cleanup Recommendation And Risk

Cleanup is reasonable because the row is known test residue with no references and no business value. It is not automatically safe to delete: QA records can be used by Record Center, audit review, or downstream trace links, and an incorrect target could remove formal history. Therefore deletion must remain an explicit human decision.

No cleanup command may be run until the user or designated data owner:

1. confirms the four identifiers above;
2. confirms that no downstream audit retention is required;
3. supplies a named authorization through `--authorized-by`;
4. approves the exact dry-run output.

R3 did not receive that authorization. `cleanup_authorized=false` and `cleanup_executed=false`.
