# Task 28A-R3E Frozen Evidence Equivalence Review

## Latest R3G Authority

The expert review and additive v2 described later in this document remain
authoritative. R3G did not modify v1, v2, accepted evidence, reviewer data, or
thresholds. The five reviewed cases remain fully covered inside Top 5; their
expert-preferred ranks are `1`, `4`, `4`, combined `2/4`, and `5`. Latest
status: `EARLY_RANKING_OPTIMIZATION_PARTIAL`.

## Decision Boundary

Frozen v1 remains byte-for-byte unchanged at SHA-256
`9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`.
No expected document ID, chunk ID, required point, query, case ID, threshold,
or case count was changed. No v2 dataset was created.

This audit identifies candidates only. It does not output
`APPROVED_EQUIVALENT` and does not prefill any expert decision field.

## Candidate Summary

| Case | Historic evidence after import | Current evidence summary | Automated status |
| --- | --- | --- | --- |
| HUAWEI-MODEL-002 | Expected EDOC chunk still active; not in raw results | Same EDOC other chunk plus new exact-model official manual states two MPPT circuits | CANDIDATE_REQUIRES_EXPERT_REVIEW |
| HUAWEI-INSULATION-004 | Expected chunk rank 7 | Official App guide and official user manual state startup self-check, insulation threshold, and no grid connection | CANDIDATE_REQUIRES_EXPERT_REVIEW |
| HUAWEI-COMM-002 | Expected chunk rank 6 | Same EDOC other chunk plus official App guide identifies the shutdown-time parameter and automatic shutdown | CANDIDATE_REQUIRES_EXPERT_REVIEW |
| HUAWEI-TEMP-001 | Expected chunk rank 7 | Official alarm-reference set covers ventilation, ambient temperature, and fan directions | CANDIDATE_REQUIRES_EXPERT_REVIEW |
| HUAWEI-GRID-003 | Expected chunk rank 6 | Same EDOC other chunks and official manuals explain LVRT, grid abnormality, and support duration | CANDIDATE_REQUIRES_EXPERT_REVIEW |

All five candidate sets pass machine-checkable provenance, status, review,
scope, citation, and required-point coverage gates. The following remain human
review items:

- exact model and firmware applicability;
- whether a multi-chunk evidence set is preferable to the historic single label;
- numeric values, units, alarm codes, and operation-order consistency;
- whether any safety condition is weakened or broadened;
- whether duplicate/current-version official manuals should be accepted as one
  evidence identity;
- whether the historic label is still the preferred evidence.

## Case Risks

### HUAWEI-MODEL-002

The current Top-5 contains direct `SUN2000-5KTL-M0` official evidence stating
two PV inputs/two MPPT circuits, including another chunk in the historic EDOC.
The machine evidence is strong, but an expert must confirm exact model/version
applicability and numeric equivalence.

### HUAWEI-INSULATION-004

Current official evidence exactly covers startup self-check, insulation
resistance below threshold, and refusal to connect to grid. One candidate is a
model-specific manual; the App/FusionSolar evidence is the safer general
candidate. Expert preference is required.

### HUAWEI-COMM-002

Current official App-guide evidence directly names the communication-link
shutdown time and automatic shutdown behavior. The same historic EDOC also
appears via a different chunk. Expert review should decide whether these form
an accepted evidence set.

### HUAWEI-TEMP-001

The current answer uses multiple official alarm chunks: the 2063 overtemperature
chunk covers ventilation and ambient temperature, while fan alarm chunks cover
fan handling. The set covers frozen points, but the expert must decide whether
combining related alarm IDs preserves the intended fault semantics.

### HUAWEI-GRID-003

The current top evidence includes the same EDOC at other chunks and states the
LVRT function directly. Expert review should confirm that parameter context and
applicable model range are equivalent to the historic label.

## Review Material

The UTF-8 CSV is:

`.runtime/task28a-r3e/expert_review/task28a_r3e_evidence_equivalence_review.csv`

It contains 24 candidate rows. These fields are intentionally blank in every
row: `expert_equivalent`, `expert_labels_accurate`,
`expert_preferred_evidence`, `expert_comment`, `reviewer_name`, `review_date`,
and `review_status`.

## Suggested Additive v2 Contract

Only after expert review, a new version may add:

- `accepted_evidence_sets`: one or more document/chunk combinations;
- `required_answer_points`: retained independently from exact chunk identity;
- `applicable_models` and firmware/version constraints;
- `numeric_constraints` and `safety_constraints`;
- source provenance and evidence-preference metadata;
- reviewer identity, review date, and decision status.

Frozen v1 must remain available for historical reproducibility. Updating labels
must never hide a real ranking defect; ranking and dataset changes require
separate versioned evidence.

## Completed Expert Review

The review is no longer pending. The authoritative CSV has SHA-256
`a0867811660c6630088cf9a15cb83e344201ab1528041bf442216b34390b7354`, reviewer
`张三`, and review date `2026-07-06`. Every required expert field is complete
for all 24 candidate rows. All five cases have a complete approved preferred
evidence set and were classified `EQUIVALENT_EVIDENCE_APPROVED`.

The resulting additive v2 retains all historic evidence and adds 12 accepted
evidence sets. A two-chunk preferred set for HUAWEI-TEMP-001 is valid only when
both chunks appear within Top-K. No case-specific production ranking change
was authorized or made. See `53_expert_reviewed_huawei_dataset_v2.md` for the
version and lineage record.
