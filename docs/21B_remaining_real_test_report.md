# Task 21B Remaining Real Test Report

## 1. Scope

Task 21B supplements real tests after Task 21A. This task does not generate a delivery package, does not update `delivery/`, does not create a zip archive, and does not introduce migrations or new product features.

The new test script is:

```text
backend/scripts/check_task21b_remaining_real_tests.py
```

The script writes machine-readable runtime evidence to:

```text
.runtime/21B_remaining_real_test_result.json
```

The runtime JSON file is intentionally not committed.

## 2. Environment Confirmation

Current environment confirmed during Task 21B:

| Item | Current state |
| --- | --- |
| Git start commit | `3cb0ee3` |
| `127.0.0.1:8000` | occupied by another local service; OpenAPI title `棱镜智教-PrismMind` |
| `127.0.0.1:8010` | Energy-Maintenance backend |
| `127.0.0.1:5432` | occupied by Docker / WSL relay |
| `127.0.0.1:55432` | Windows native PostgreSQL process |
| PostgreSQL Windows service | `postgresql-x64-16` remains `Stopped / Disabled` |
| Alembic current | `20260601_0003 (head)` |

The backend and tests used:

```text
TASK21B_API_BASE_URL=http://127.0.0.1:8010/api
DATABASE_URL=postgresql+psycopg://energy_user:***@127.0.0.1:55432/energy_maintenance
```

## 3. Task 21B Script Result

Final script result:

```text
status: passed
total: 27
passed: 27
blocked: 0
partial: 0
failed: 0
skipped: 0
```

Covered items:

| Area | Result |
| --- | --- |
| Default/current port difference | passed |
| PostgreSQL direct connection | passed |
| Role setup | passed |
| Frontend page action/API alternative matrix | passed |
| TXT upload/parse/retrieval | passed |
| MD upload/parse/retrieval | passed |
| DOCX upload/parse/retrieval | passed |
| PDF upload/parse/retrieval | passed |
| Pending review excluded from retrieval | passed |
| Approved document included in retrieval | passed |
| Reparse approved document | passed |
| Archived document excluded from retrieval | passed |
| Viewer upload blocked | passed |
| Viewer archive-review blocked | passed |
| Viewer task creation blocked | passed |
| Soft test data cleanup | passed |

## 4. Multi-format Knowledge Upload Evidence

The script uploaded real files through `/api/knowledge/documents/upload`, verified `parse_status=parsed`, queried chunks, approved documents, and verified retrieval references.

| Format | Document title | Chunk count | Retrieval trace |
| --- | --- | --- | --- |
| txt | `Task21B_20260630123612 Huawei SUN2000 TXT` | 1 | `qa_20260630043616_3a7564ea32` |
| md | `Task21B_20260630123612 Sungrow SG MD` | 1 | `qa_20260630043616_c2e542152f` |
| docx | `Task21B_20260630123612 Huawei FusionSolar DOCX` | 1 | `qa_20260630043617_c655f142fc` |
| pdf | `Task21B_20260630123612 Huawei SUN2000 PDF` | 1 | `qa_20260630043617_1677c61688` |

Notes:

- DOCX was generated with the existing `python-docx` dependency.
- PDF was a text-based minimal PDF generated inside the test script.
- The test verified that chunk content contained the unique Task 21B phrase for each format.

## 5. Review Status and Retrieval Impact

The script verified:

1. A freshly uploaded `pending_review` document did not appear in retrieval references.
2. After expert approval, the same document appeared in retrieval references.
3. Reparse returned `parse_status=parsed` and a positive `chunk_count`.
4. After archive, the document no longer appeared in retrieval references.

Approved retrieval trace:

```text
qa_20260630043617_cc3cd99032
```

Archived exclusion trace:

```text
qa_20260630043618_9eebece13f
```

## 6. Frontend Button/API Verification Mode

No browser click result is claimed in this report.

Task 21B used an alternative verification method:

```text
frontend source action matrix + live backend OpenAPI matching + real network API workflows
```

The script scanned Vue pages for:

- `@click`
- `@submit`
- `RouterLink`
- imported API function usage

Result:

```text
pages_with_actions: 26
pages_with_api: 17
frontend API calls: 67
all frontend API calls still matched backend OpenAPI
```

This proves source-level button/form/API wiring plus backend endpoint availability, but it is not presented as a real browser click test.

## 7. Permission Boundary Evidence

Verified with real viewer token:

- viewer cannot upload a knowledge document
- viewer cannot archive a review document
- viewer cannot create a maintenance task

Task 21A had already covered additional viewer/RBAC checks for review, OCR trigger, KG write, task assignment, and device write.

## 8. Cleanup Evidence

The script performed soft cleanup only:

- archived TXT test document
- archived MD test document
- archived DOCX test document
- archived PDF test document
- archived review-effect document
- disabled generated engineer/expert/viewer test users

No hard deletion of formal demo data was performed.

## 9. Additional Checks

Commands executed after Task 21B script:

```text
cd backend
uv run python -m compileall app scripts
```

Result: passed.

```text
cd backend
DATABASE_URL=postgresql+psycopg://energy_user:energy_password@127.0.0.1:55432/energy_maintenance
uv run python -m alembic -c alembic.ini current
```

Result: passed, `20260601_0003 (head)`.

```text
cd frontend
npm.cmd run build
```

Result: passed.

```text
powershell -ExecutionPolicy Bypass -File .\scripts\final_smoke_test.ps1 -BaseUrl http://127.0.0.1:8010 -IncludeRetrievalQuery
```

Result: passed, 23 checks, 0 failed.

The final smoke command still printed local conda profile encoding noise after the successful smoke output. The command exit code was 0, and the smoke summary showed passed.

## 10. No Delivery Package Confirmation

This task did not:

- generate delivery zip
- update `delivery/`
- execute packaging scripts
- create migrations
- run `alembic upgrade head`
- introduce Docker
- introduce SQLite
- install OCR
- download local model files

## 11. Known Issues

- Default port `8000` is still occupied by another local service.
- Default PostgreSQL port `5432` is still occupied by Docker / WSL relay.
- PostgreSQL Windows service remains `Stopped / Disabled`; Task 21B used the native PostgreSQL process on `55432`.
- Browser click testing was not performed. The accepted alternative used static frontend action/API mapping and real network workflows.
- OCR, cloud OpenAI-compatible model, and local llama.cpp remain blocked/disabled external capabilities and are not claimed as passed.

## 12. Conclusion

Task 21B completed the requested remaining real tests without producing a delivery package. The main remaining first-run operational concern is environment normalization: free or remap default ports and repair the Windows PostgreSQL service if final local demonstration must run on `8000` and `5432`.
