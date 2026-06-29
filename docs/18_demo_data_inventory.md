# Task 16 Demo Data Inventory

Demo data is created by:

```powershell
cd backend
uv run python scripts\seed_final_demo_data.py
```

The script is idempotent. It uses fixed usernames, device codes, document titles, source markers, and trace IDs. It does not overwrite user-uploaded files.

## Users

- `admin`
- `expert`
- `engineer`
- `viewer`

## Devices

- `EM-DEMO-HW-SUN2000-01`: Huawei SUN2000 demo inverter.
- `EM-DEMO-HW-FUSIONSOLAR-01`: Huawei FusionSolar communication demo inverter.
- `EM-DEMO-SG-01`: Sungrow SG demo inverter.
- `EM-DEMO-SG-MPPT-01`: Sungrow SG MPPT low-generation demo inverter.

## Knowledge Documents

All seeded documents use `source=final_demo_seed`.

- `Final Demo Huawei SUN2000 Insulation Alarm Manual`
- `Final Demo Huawei FusionSolar Communication Case`
- `Final Demo Sungrow SG Communication Alarm SOP`
- `Final Demo Sungrow SG Over Temperature Case`
- `Final Demo Sungrow SG MPPT Low Generation Case`
- `Final Demo Converted SUN2000 Field Contribution Document`: converted from a seeded frontline contribution.

## Records and Tasks

- QA records:
  - `FINAL-DEMO-QA-LOW-INSULATION`
  - `FINAL-DEMO-QA-FUSIONSOLAR-COMM`
- Diagnosis record:
  - `FINAL-DEMO-DIAG-SG-COMM`
- Maintenance tasks:
  - `Final Demo Huawei SUN2000 insulation alarm verification`
  - `Final Demo Sungrow SG over temperature in-progress task`
- Maintenance history:
  - A completed communication recovery record linked to `FINAL-DEMO-DIAG-SG-COMM`.

## Review and Correction Data

- Submitted contribution:
  - `Final Demo Pending Knowledge Contribution`
- Converted contribution:
  - `Final Demo Converted Huawei SUN2000 Field Contribution`
  - linked document: `Final Demo Converted SUN2000 Field Contribution Document`
  - review actions: `approve`, `convert_to_document`
- Pending correction:
  - source trace `FINAL-DEMO-QA-LOW-INSULATION`

## Cleanup

Development/test data audit:

```powershell
cd backend
uv run python scripts\cleanup_dev_test_data.py
```

This is dry-run by default. Explicit cleanup requires:

```powershell
uv run python scripts\cleanup_dev_test_data.py --execute --confirm CLEAN_DEV_TEST_DATA
```

The cleanup script soft-archives safe rows and skips rows that could break foreign keys.

## Task 17B Media Evidence

The stable seed does not fabricate OCR text or image recognition results. Media evidence used during Task 17B acceptance is uploaded through `/api/media/upload` and may be linked to a demo device, diagnosis, QA trace, or task through existing columns and JSONB metadata.

Supported upload extensions are `jpg`, `jpeg`, `png`, and `webp`. OCR status is expected to remain `disabled` or `not_configured` unless a real OCR provider is configured and verified later.

## Task 18B Contribution Flow Data

The seed includes repeatable contribution records for final demo:

- `Final Demo Pending Knowledge Contribution`: submitted status, awaiting expert review.
- `Final Demo Converted Huawei SUN2000 Field Contribution`: converted status, linked to an approved knowledge document and generated chunks.

The dynamic contribution flow checker creates temporary records prefixed with `Task18B_Flow_`. The cleanup script recognizes `Task18B` by default and remains dry-run unless `--execute --confirm CLEAN_DEV_TEST_DATA` is explicitly supplied.
