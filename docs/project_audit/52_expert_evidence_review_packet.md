# Task 28A-R3F Expert Evidence Review Packet

## Latest R3G Authority

The historical `BLOCKED_EXPERT_REVIEW_PENDING` section below records the state
before the completed expert CSV. Review is now complete and v2 remains frozen
at SHA-256
`f9a000f45fd12571adebea90b52b97cf4cf5fe9dba01a8c33f80de5b2db68d68`.
R3G did not change expert decisions. Latest project status is
`EARLY_RANKING_OPTIMIZATION_PARTIAL` due only to early ranking.

## Status

`BLOCKED_EXPERT_REVIEW_PENDING`

Task 28A-R3F is locked in Mode A. The existing expert-review CSV contains the
24 expected candidate rows for five failed cases, but all required expert
decision fields are empty. No expert conclusion has been inferred or filled by
automation.

## Review Inputs

- Expert CSV: `.runtime/task28a-r3e/expert_review/task28a_r3e_evidence_equivalence_review.csv`
- CSV SHA-256: `1c821d818e3cf412404565ccd84ab7d1b6207eabd246a0bfebe4c4eb75c1fd54`
- Candidate rows: `24`
- Cases: `5`
- Cases requiring review:
  - `HUAWEI-MODEL-002`
  - `HUAWEI-INSULATION-004`
  - `HUAWEI-COMM-002`
  - `HUAWEI-TEMP-001`
  - `HUAWEI-GRID-003`

The generated review materials are:

- Markdown: `.runtime/task28a-r3f/expert_packet/task28a_r3f_expert_review_packet.md`
- HTML: `.runtime/task28a-r3f/expert_packet/task28a_r3f_expert_review_packet.html`
- CSV validation: `.runtime/task28a-r3f/expert_validation/csv_validation.json`
- Mode A result: `.runtime/task28a-r3f/validation/mode_a_result.json`

Each packet presents the query, required answer points, historic evidence,
pre/post rank evidence, current Top-10 results, and the candidate evidence
details needed for human review. It does not contain an approval decision.

## Frozen Dataset Boundary

- Frozen v1: `backend/tests/fixtures/task27a_huawei_sun2000_engineering_candidate_v1.json`
- Frozen v1 SHA-256: `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`
- Frozen v1 modified: `no`
- Versioned v2 created: `no`
- Ranking implementation changed: `no`
- Formal database writes: `0`
- QA records added: `0`
- External provider calls: `0`
- Vector rebuilds: `0`

Mode B is not authorized until a real Huawei PV-inverter maintenance expert
completes every required decision field for all five cases.

## Evidence Note

The requested R3E path
`.runtime/task28a-r3e/diagnostics/regression_failure_evidence.json` is absent.
No substitute file was fabricated. R3E's
`.runtime/task28a-r3e/comparison/per_case_rank_drift.json` is the authoritative
rank-drift input used by the review packet. The older R3D regression evidence
remains available only as supporting historical evidence.

## Expert Completion Instructions

A real Huawei PV-inverter maintenance expert must edit the existing CSV in
place. Do not modify automatically generated case, query, rank, document,
chunk, provenance, or evidence-text fields.

Complete these fields for every candidate row:

- `expert_equivalent`: `YES`, `NO`, or `PARTIAL`
- `expert_labels_accurate`: `YES`, `NO`, or `NEEDS_UPDATE`
- `expert_preferred_evidence`: candidate evidence ID or accepted evidence set
  from the same case
- `expert_comment`: detailed model, firmware, numeric, safety, and
  operation-order reasoning
- `reviewer_name`: real reviewer identity
- `review_date`: actual review date
- `review_status`: `APPROVED`, `REJECTED`, or `NEEDS_MORE_EVIDENCE`

After the CSV is fully completed, Task 28A-R3F may be rerun from its validation
gate. Only then may it classify evidence-equivalence approvals, ranking defects,
or unresolved cases and decide whether a versioned v2 dataset is justified.

## Stop Decision

The task stops at Mode A. The five cases remain unresolved pending real expert
review. No dataset relabeling, ranking repair, database operation, or acceptance
claim is permitted from the current empty review state.

## Task 28A-R3F Completion Addendum

The earlier stop condition has been cleared by the completed expert CSV. The
reviewer is `张三` (confirmed by the user as the real name), the review date is
`2026-07-06`, and all seven expert fields are complete for 24/24 rows.

Validation classified all five cases as equivalent-evidence-approved, with
zero ranking-repair-required and zero unresolved cases. Frozen v1 was not
modified. Additive v2 and its schema were generated deterministically and are
documented in `53_expert_reviewed_huawei_dataset_v2.md`.

This clears the evidence-review blocker only. The post-import v2 early-ranking
gate still fails, so the project status remains
`FORMAL_IMPORT_COMMITTED_RAG_COVERAGE_PARTIAL` as documented in
`54_post_expansion_ranking_and_dual_gate_acceptance.md`.
