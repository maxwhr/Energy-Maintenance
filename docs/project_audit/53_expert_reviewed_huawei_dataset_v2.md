# Task 28A-R3F Expert-reviewed Huawei Dataset v2

## Task 28A-R3G Integrity Confirmation

R3G reverified this v2 byte-for-byte at SHA-256
`f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.
No accepted evidence set, reviewer field, query, threshold, document ID, or
chunk ID changed. Production leakage scan found no runtime use of this fixture
or its expert labels.

## Expert Review Input

- Source CSV: `.runtime/task28a-r3e/expert_review/task28a_r3e_evidence_equivalence_review.csv`
- CSV SHA-256: `a0867811660c6630088cf9a15cb83e344201ab1528041bf442216b34390b7354`
- Reviewer: `张三` (confirmed by the user as the reviewer's real name)
- Review date: `2026-07-06`
- Shape: 24 candidate rows, 29 columns, five affected cases
- Required expert fields: complete for every row

The only machine-field representation change was Excel's normalization of
`source_official` from `true` to `TRUE`. Validation canonicalized this boolean
case without rewriting the expert CSV. All other frozen machine fields matched
the R3E rank-drift evidence exactly.

## Decision Classification

| Case | Decision | Approved rows | Rejected rows | Preferred evidence |
| --- | --- | ---: | ---: | --- |
| HUAWEI-MODEL-002 | EQUIVALENT_EVIDENCE_APPROVED | 3 | 2 | `7aebd737-3176-4d43-9617-a21027670a05` |
| HUAWEI-INSULATION-004 | EQUIVALENT_EVIDENCE_APPROVED | 2 | 3 | `e029609d-ec3a-420e-bd62-45476bfd19bf` |
| HUAWEI-COMM-002 | EQUIVALENT_EVIDENCE_APPROVED | 3 | 2 | `ccd46996-8dd4-4082-b232-7ee7fdb5e4ca` |
| HUAWEI-TEMP-001 | EQUIVALENT_EVIDENCE_APPROVED | 2 | 2 | combined set `4ec166a4-80cd-4cf0-a37e-60a2b4e2468b` + `a6b65efe-8971-4e60-91f6-3266f4acd735` |
| HUAWEI-GRID-003 | EQUIVALENT_EVIDENCE_APPROVED | 3 | 2 | `85199933-a22a-4bfd-a860-329b944c7b76` |

Equivalent-evidence cases: 5. Ranking-repair-required cases: 0. Unresolved
cases: 0. Rejected candidate rows remain excluded alternatives and do not
invalidate a case whose approved preferred evidence completely covers the
frozen answer points.

## Versioned Dataset

- Frozen v1 remains unchanged:
  `backend/tests/fixtures/task27a_huawei_sun2000_engineering_candidate_v1.json`
- v1 SHA-256:
  `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`
- Additive v2:
  `backend/tests/fixtures/task27a_huawei_sun2000_engineering_candidate_v2.json`
- v2 schema:
  `backend/tests/fixtures/task27a_huawei_sun2000_engineering_candidate_v2.schema.json`
- v2 SHA-256:
  `f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`

V2 retains all 30 v1 cases and their historic evidence, then adds 12 accepted
expert evidence sets across the five reviewed cases. A multi-chunk accepted set
matches only when every chunk in the set is present within Top-K. The dataset's
top-level `expert_reviewed` remains false because only five of 30 cases have
expert review; reviewed cases carry their own review metadata.

Generation was rerun and produced the same v2 hash. The environment does not
contain the optional `jsonschema` package, so no library-based schema command
was installed or executed; the generator's built-in structural, lineage, set,
and hash checks passed.

## Safety Boundary

No production ranking branch, formal database row, QA record, provider log,
vector run, schema, or Alembic revision was changed. The accepted evidence is
versioned evaluation metadata, not a formal-corpus mutation.
