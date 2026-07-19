# Formal Test Residue Inventory Revalidated

## Status

`RESIDUE_CLASSIFICATION_REQUIRES_USER_REVIEW`

This was a formal-database transaction-read-only discovery and planning pass.
It did not delete, update, archive, or otherwise modify a formal row.

## Results

| Classification | Count | Action |
| --- | ---: | --- |
| `CONFIRMED_TEST_RESIDUE` | 1 | Future exact-ID review only |
| `LIKELY_TEST_REQUIRES_REVIEW` | 434 | Retain pending individual review |
| `PRODUCTION_OR_AUDIT_RETAIN` | 15 | Retain |
| `UNKNOWN_NO_ACTION` | 2689 | No action |

The `3138` raw keyword candidates are a deliberately broad discovery set and
must not be interpreted as deletion candidates.

## Protected Records

- QA `4a9eeab8-91de-43bb-90ec-78a3d6bba7be` remains present. This task did not
  use the historical deletion token.
- Knowledge Chunk `b31b7107-9306-4286-b9c3-a9036212b5ac` is retained. Its
  `17A` text is a rated maximum output-current value from an approved Huawei
  manual, not a test marker.
- The protected `17A` object had `76` read-only dependency findings and must
  not be included in a future cleanup Apply.

## Cleanup Plan

- Plan: `docs/project_audit/task28a_formal_test_residue_cleanup_plan.json`.
- Plan SHA-256:
  `2ae7381be073a7864073342e33e639b381dee03597200f0582b76f042152be1e`.
- State: `DRY_RUN_READY_AWAITING_EXPLICIT_APPROVAL`.
- Formal rows modified: `0`.
- Formal rows deleted: `0`.

Any future cleanup requires a new explicit approval bound to the current plan
hash, a fresh `pg_dump -Fc`, exact dependency revalidation, and before/after
Record Center verification.
