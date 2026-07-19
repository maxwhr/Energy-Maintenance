# Task 25B-R3-DEV-R3 Vector-heavy Grounding Audit

## Scope and integrity

- Train/dev only; test_v3 was not read or used: `False`.
- Cases reviewed: 88.
- This is an evidence audit, not a label expansion. It preserves weak and ambiguous cases instead of promoting adjacent or same-document chunks.

## Result

| Status | Count |
| --- | ---: |
| GROUNDED_STRONG | 29 |
| GROUNDED_MODERATE | 0 |
| AMBIGUOUS_SECTION | 19 |
| GROUNDING_WEAK | 40 |
| Usable Canary cases | 29 |

The historical R2 train/dev vector-heavy labels contribute 40 `GROUNDING_WEAK` rows. The new source-only candidate set exposed 19 `AMBIGUOUS_SECTION` rows because the same abstract semantic signature labelled multiple source chunks. Those rows are not valid positive Chunk labels and must not be used to claim a passing Canary.
# R4 follow-up

R3 remains immutable evidence (29 strong, 19 ambiguous, 40 weak). R4 does not rewrite those labels; it creates a separate source-unit Train/Dev baseline with an ambiguity-free topic discriminator and dual engineering checks. See `25B_R3_DEV_R4_grounded_benchmark_report.md`.
