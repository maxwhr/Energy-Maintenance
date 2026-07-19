# Task 28A-R3G Generic Ranking Optimization and Ablation

## Final Candidate

Selected: `A1_scope_snapshot_plus_A2_precomputed_features_safe_rollback`.

Rejected: `A7_complementary_evidence_selection`.

The selected candidate is performance-only at the current production ranking
boundary. It retains generic model/alarm/parameter/normalization features for
future work, but it does not activate the rejected ranking changes.

## Development Ablations

| Ablation | R@1 | R@3 | R@5 | MRR | nDCG@5 | Failed | P95 ms | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A0 baseline | .516667 | .716667 | .750000 | .610278 | .645567 | 15 | 6290.926 | baseline |
| A1 Scope snapshot | .516667 | .716667 | .750000 | .610278 | .645567 | 15 | 3441.820 | retain |
| A2 precomputed features | .516667 | .716667 | .750000 | .610278 | .645567 | 15 | 3539.119 | retain structure |
| A3 variant normalization | .533333 | .716667 | .750000 | .618611 | .651718 | 15 | 3392.512 | reject |
| A4 strict entity ranking | .533333 | .766667 | .766667 | .638889 | .671822 | 14 | 1927.008 | reject |
| A5 parent context | .516667 | .750000 | .783333 | .630556 | .669511 | 13 | 2023.094 | reject |
| A6 duplicate diversity | .516667 | .750000 | .783333 | .630556 | .669511 | 13 | 2126.731 | reject |
| A7 complementary evidence | .583333 | .816667 | .833333 | .695000 | .730451 | 10 | 2248.366 | reject |
| A8 safe rollback | .516667 | .716667 | .750000 | .610278 | .645567 | 15 | 3246.765 | final |

All ablations had citation validity `1.0`, safety coverage `1.0`, no
cross-vendor result, no QA persistence, no provider call, no vector run, and no
database write.

## One-shot Holdout

The holdout was run exactly once on A7:

- R@1/R@3/R@5: `.428571/.523810/.523810`
- MRR/nDCG@5: `.460317/.476190`
- citation validity/support: `1.0/.904762`
- required-point coverage: `.928571`
- failed cases: `11`
- P50/P95: `790.119/1800.059 ms`

This is `RANKING_OVERFIT_DETECTED` for the rejected A7 candidate. Per the
one-shot rule, the final safe rollback was not evaluated again on holdout.

## Hydration and Cache

- SQL Scope hydration: maximum one database read per cache miss.
- Development evaluation: 58 cache hits, 7 misses.
- Cache key includes Scope fields, document IDs, and corpus revision.
- Snapshot contents are immutable tuples/mappings.
- Knowledge and review service commit paths invalidate the cache.
- Candidate normalized text, model identifiers, alarm codes, parameter terms,
  numeric/unit tokens, title/section text, and content fingerprints are
  precomputed once per snapshot.

## Regression Decision

A7 four-cell behavior regressed both pre-import and post-import frozen results,
so A3-A7 ranking behavior was removed. The final A1+A2 safe candidate exactly
reproduces all four pre-change functional cells and improves formal-v2
aggregate P95 from `6224.023 ms` to `3074.891 ms` (`-50.5964%`).

Production leakage scan found no expert Case ID, frozen fixture path,
accepted-evidence runtime read, or reviewer-field runtime read.

## R3H Contract Repair Addendum

R3H replaced the rank-only keyword handoff with `KeywordCandidateHit`, retained
normalized relevance, selected the best score-aware vote per physical channel,
and added direct-evidence monotonic protection. The observed normal-path score
fallback ratio is zero; average primary votes per evidence changed from
`2.305876` to `1.208986`; non-monotonic demotions changed from `2` to `0`.

The candidate is rejected for formal activation: one-shot Holdout R@3/R@5 were
`0.840000/0.880000`, scope isolation was `0.700000`, and frozen pre-import
no-regression gates failed. No Holdout-informed tuning was performed.
