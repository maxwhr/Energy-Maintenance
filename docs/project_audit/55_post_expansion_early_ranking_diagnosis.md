# Task 28A-R3G Post-expansion Early-ranking Diagnosis

## Final Status

`EARLY_RANKING_OPTIMIZATION_PARTIAL`

The post-import expert-v2 corpus still passes complete Top-5 evidence,
citation, required-point, safety, and scope-isolation checks, but it does not
meet every frozen early-ranking threshold. No frozen label, formal row, or
schema was changed.

## Independent Evaluation Data

- Development set: `task28a_r3g_dev_v1`, 65 cases, SHA-256
  `431fac8f26a3c6933810948b6a75283aea8a2d45b8613f7ffad59ef4cf9b54fe`.
- One-shot holdout: `task28a_r3g_holdout_v1`, 25 cases, SHA-256
  `924ee29b7f109f2823230c3f43dd694a112f3818131702be9fc8922c4df5d455`.
- Development, holdout, and frozen-30 normalized query overlap: zero.
- Both datasets were generated from approved/active Huawei corpus evidence
  without an LLM. Their identifiers are confined to `.runtime` artifacts.

## Pipeline Diagnosis

The 65-case development trace records query understanding, generated variants,
raw candidates, fusion, guards, deterministic rerank, citations, final ranks,
score components, and hydration telemetry. Evidence is in
`.runtime/task28a-r3g/diagnostics/full_pipeline_rank_trace.json`.

The main findings are:

- the 1,558-chunk Scope was repeatedly hydrated and normalized in the old
  path, making local keyword work the dominant latency component;
- exact model, alarm, parameter, title, section, and source metadata were not
  available as one reusable precomputed feature object;
- near-duplicate and complementary evidence handling can improve a development
  set but is sensitive to unseen-query distribution;
- expert-v2 evidence is complete inside Top 5, while several expert-preferred
  sets remain at ranks 4 or 5.

## Safe Resolution

The retained implementation builds an immutable Scope snapshot, binds cache
keys to the resolved Scope and corpus revision, invalidates after committed
knowledge/review changes, and precomputes generic text features once per
candidate. It does not alter final ranking weights or use evaluation labels.

The rejected A3-A7 ranking behavior was rolled back after its one-shot holdout
and four-cell regression failed. The holdout was not rerun and was not used to
tune the safe rollback.

## Data Protection

Both PostgreSQL instances ran with `transaction_read_only=on`. All protected
table deltas, Huawei Scope deltas, QA additions, provider calls, vector runs,
schema changes, and Alembic changes were zero. Frozen v1 and expert-v2 hashes
remain unchanged.

## R3H Superseding Diagnosis

R3H localized score-provenance loss in the repository/hydration to
multi-query contract and two non-monotonic direct-evidence demotions. The
variant-vote multiplication replay and requested-information-overmatch scan did
not prove those hypotheses as causal.

The repaired candidate passed a new 115-case Dev set but failed a fresh
60-case one-shot Holdout and regressed the frozen pre-import cells. The current
status is therefore `RANKING_OVERFIT_DETECTED`, superseding the prior
`EARLY_RANKING_OPTIMIZATION_PARTIAL` status for ranking acceptance purposes.
