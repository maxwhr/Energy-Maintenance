# Task 28A Product Closure And Ranking Deferment

## Product Decision

`FORMAL_HUAWEI_RAG_FUNCTIONAL_ACCEPTANCE_PASSED`

Task 28A is closed for the Huawei SUN2000 functional product gate: real formal
knowledge retrieval returns traceable citations, the expert-v2 evidence gate
has zero failures, safety and Scope boundaries pass, formal data is unchanged,
and the isolated knowledge lifecycle works end to end.

## Ranking Decision

`ENGINEERING_EARLY_RANKING_RESEARCH_DEFERRED`

Historical R3H status remains `RANKING_OVERFIT_DETECTED`. R3H Recall@1,
Recall@3, MRR, and nDCG results are not accepted product claims. The C1-C5
detour was stopped under `R3H_ABLATION_DETOUR_STOPPED`; no Holdout was rerun
and no post-Holdout tuning occurred.

The accepted product baseline is
`A1_scope_snapshot_plus_A2_precomputed_features_safe_rollback`. It preserves
immutable Scope snapshots, cache invalidation, normalized text/model/alarm/
parameter features, content fingerprints, and bounded Scope SQL behavior,
without activating the rejected R3H ranking behavior.

## Closure Evidence

- Post-import/v2: R@5 `1.0`, citation validity/support `1.0`, required coverage
  `1.0`, failed cases `0`, safety/Scope/abstention `1.0`.
- Formal 10 documents: `10/10`; Amphenol: `3/3`.
- Formal database writes/deletes: `0`; QA preview delta: `0`; Provider,
  embedding, and vector deltas: `0`.
- Isolated knowledge lifecycle and browser acceptance: passed.
- Frozen v1/v2 Hashes: unchanged.
- Formal residue cleanup: plan only, no Apply.

## Remaining Non-blocking Work

A future independent engineering study may revisit early ranking only with a
new untouched Holdout. It must not reuse the consumed R3G/R3H Holdouts or tune
against frozen failures. This work is optional and does not reopen the Task 28A
product functional closure.
