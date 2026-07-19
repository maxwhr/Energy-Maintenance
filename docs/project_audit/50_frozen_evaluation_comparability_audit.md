# Task 28A-R3E Frozen Evaluation Comparability Audit

## Latest R3G Comparability Addendum

R3G reran all four cells after the safe rollback. Functional metrics exactly
match the R3F matrix, pre-import v1/v2 have no regression, and frozen fixture
hashes are unchanged. Only latency changed materially: formal-v2 aggregate P95
fell from `6224.023 ms` to `3074.891 ms`. A7 was rejected after failing the
one-shot holdout and four-cell regression; the holdout was not rerun or used
for tuning. Latest status: `EARLY_RANKING_OPTIMIZATION_PARTIAL`.

## Status

Primary causal classification: `CORPUS_EXPANSION_RANKING_COMPETITION_CONFIRMED`.

Delivery decision: `EVIDENCE_EQUIVALENCE_REVIEW_REQUIRED`.

This is not a passed frozen-gate result. The post-import corpus still fails the
unchanged v1 exact-evidence gate. No ranking code, frozen label, formal row, or
schema was changed during this audit.

## Artifact And Fixture Identity

- Fixture: `task27a_huawei_sun2000_engineering_candidate_v1`, version `1.0.0`.
- Fixture SHA-256 before and after:
  `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`.
- Historical artifact:
  `.runtime/task27a/keyword_evaluation_exp5_normalized.json`.
- Historical artifact SHA-256:
  `4bf9b28a2328fc388da717b99d426b222f097a9103a510ea43c35ac35d4c6d4f`.
- The historical JSON is parseable and contains the expected dataset identity,
  30 cases, 28 evidence cases, two abstentions, metrics, zero failures, and the
  `372/4791/2598` database baseline.
- Historical `generated_at`, code hashes, exact candidate-depth number,
  concurrency, timeout, warmup, and random seed were not recorded. They remain
  `UNKNOWN_NOT_RECORDED`; no values were invented.

Current file-level SHA-256 values and the non-sensitive execution contract are
recorded in:

- `.runtime/task28a-r3e/baseline/current_evaluator_fingerprint.json`
- `.runtime/task28a-r3e/baseline/historical_evaluator_fingerprint.json`
- `.runtime/task28a-r3e/comparison/comparable_run_configuration.json`

## Pre-import Restore

The backup
`.runtime/task28a-r3b/backups/energy_maintenance_preapply_retry_20260718_150154.dump`
was revalidated at SHA-256
`2353bd58e043425c44b7a5de849850baba8bd5c49afbce941d88f9641da9fea7`.
`pg_restore --list` returned 629 entries.

It was restored only to the project-local cluster:

- Data directory: `.runtime/task28a-r3e/postgres-preimport/data`
- Host/port: `127.0.0.1:55434`
- Database: `energy_maintenance` in the isolated comparison cluster
- PostgreSQL: 16.14, UTF-8, SCRAM-SHA-256
- Baseline: 372 documents, 4,791 chunks, 2,598 QA records
- Alembic: `20260712_0015`

The 13 v3 non-target business counts, `external_api_call_logs=676`, and
`vector_index_runs=88` also match the frozen pre-import baseline. The cluster
was restarted with `default_transaction_read_only=on`; an UPDATE probe failed
with `ReadOnlySqlTransaction`.

## Comparable Execution Contract

Both groups used the same current worktree, Python environment, fixture, scope,
and direct evaluator process. The only variables were port and corpus contents.

- Scope: `huawei_sun2000_competition_v1`
- Functional `top_k`: 5
- Candidate depth: 50 per channel; fusion limit: 150
- Query variant jobs observed: 2 to 5
- Deterministic rerank: enabled
- Dedicated/LLM rerank: disabled
- Answer mode: rule-based grounded answer
- Providers, embedding, DashVector, OCR, and real APIs: forced off
- Persistence: false
- Evaluator concurrency: 1; internal query-variant concurrency: 1
- Warmup: three queries per database
- Complete runs: three per database
- Functional metrics: first complete run
- Performance: all 90 Case latencies across three runs; no fastest-run selection
- Top-10 diagnostics: separate requests, excluded from frozen metrics

## Three-way Functional Results

| Metric | Historical pre-import | Pre-import current code | Post-import current code |
| --- | ---: | ---: | ---: |
| Recall@1 | 0.750000 | 0.750000 | 0.392857 |
| Recall@3 | 0.964286 | 0.964286 | 0.714286 |
| Recall@5 | 1.000000 | 1.000000 | 0.821429 |
| MRR | 0.854167 | 0.854167 | 0.560714 |
| nDCG@5 | 0.891228 | 0.891228 | 0.626207 |
| Citation validity | 1.000000 | 1.000000 | 1.000000 |
| Citation support | 1.000000 | 1.000000 | 0.821429 |
| Required answer point coverage | 1.000000 | 1.000000 | 1.000000 |
| Failed cases | 0 | 0 | 5 |

Current code exactly reproduces every historical functional metric on the
pre-import corpus. On the post-import corpus it exactly reproduces the existing
R3D functional metrics and the same five failures. This rules out current-code
functional drift and R3D execution mismatch as the primary cause.

## Rank Drift

Across the 28 in-scope cases, classifications are:

- `NO_CHANGE`: 14
- `PUSHED_BELOW_TOP1`: 7
- `SMALL_RANK_SHIFT`: 1
- `PUSHED_BELOW_TOP3`: 1
- `PUSHED_BELOW_TOP5`: 5

All five failing expected chunks still exist, remain active/approved/in-scope,
and have the same content SHA-256 before and after import. None was deleted,
rewritten, archived, or invalidated. Their post-import positions are:

| Case | Pre-import rank | Post-import Top-10 rank | Raw rank | New chunks in Top 10 |
| --- | ---: | ---: | ---: | ---: |
| HUAWEI-MODEL-002 | 1 | not surfaced | not surfaced | 7 |
| HUAWEI-INSULATION-004 | 2 | 7 | 6 | 5 |
| HUAWEI-COMM-002 | 1 | 6 | 6 | 7 |
| HUAWEI-TEMP-001 | 1 | 7 | 8 | 7 |
| HUAWEI-GRID-003 | 3 | 6 | 8 | 7 |

The full 28-case data is in
`.runtime/task28a-r3e/comparison/per_case_rank_drift.json`.

## Evidence-equivalence Findings

Each failing Top-5 set is Huawei official, parsed, active, approved, in scope,
and collectively covers every frozen required answer point. Examples include
the same EDOC at a different chunk, a newly imported official copy of the same
manual, or a newer applicable official manual. Consequently all five are
`CANDIDATE_REQUIRES_EXPERT_REVIEW`, not approved equivalents.

There are zero confirmed technical relevance failures at this stage, but this
must not be read as zero possible ranking defects: model applicability,
numeric/safety equivalence, and preferred evidence remain human decisions.
The v1 gate remains failed until an authorized ranking task or expert-reviewed
versioned dataset resolves that distinction.

## Performance

| Result | P50 ms | P95 ms | Policy |
| --- | ---: | ---: | --- |
| Historical | 1,104.635 | 1,658.421 | one historical final run |
| Pre-import current | 3,120.881 | 4,371.010 | 90 cases, three runs |
| Post-import current | 6,634.581 | 10,066.550 | 90 cases, three runs |

Historical timing is not fully comparable because historical concurrency,
warmup, and process parameters were not recorded. The pre/post current-code
comparison is controlled and comparable.

Although total database chunks rose only 19.6%, the eligible Huawei scope grew
from 621 to 1,558 chunks (150.9%). Median candidate hydration rose from 0.245 ms
to 709.791 ms and median keyword-variant work rose from 2,958.485 ms to
6,080.504 ms. Hydration cache hits dropped from 46/90 to 18/90 because the
five-second TTL expires more often once each request takes longer. Provider,
embedding, vector, answer assembly, and serialization are not the dominant
delta. The performance root-cause candidate is repeated full-scope hydration
and local per-variant scoring over the much larger eligible scope. No
performance optimization was made.

## Zero-write Reconciliation

Both databases remained unchanged across warmups, three full runs, and Top-10
diagnostics:

- Formal document/chunk/QA deltas: 0/0/0
- Provider log delta: 0
- Vector run delta: 0
- Schema/Alembic changes: 0
- Fixture changes: 0

## Recommendation

Do not edit frozen v1. Ask a Huawei inverter-maintenance expert to review the
24 candidate rows in
`.runtime/task28a-r3e/expert_review/task28a_r3e_evidence_equivalence_review.csv`.
After review, choose either `Task 28A-R3F-RANKING`, an additive expert-reviewed
`Task 28A-R3F-DATASET-V2`, or both. A v2 must retain v1 and support accepted
evidence sets, required points, model applicability, safety constraints, and
source provenance.

## Teardown

The task-started formal instance on 55432 and isolated comparison instance on
55434 were stopped. Ports 55432, 55433, and 55434 are free. Windows service
`postgresql-x64-16` remains `Stopped / Disabled`. The restored comparison data
and source backup were retained; the random temporary administrator password
was not persisted.

## Task 28A-R3F Four-cell Addendum

The completed expert CSV enabled an additive v2 without modifying frozen v1.
All four controlled cells were rerun three times with identical warmup,
concurrency, Top-K, keyword-only, no-persistence, and no-provider parameters.

| Cell | R@1 | R@3 | R@5 | MRR | nDCG@5 | Failed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pre-import v1 | 0.750000 | 0.964286 | 1.000000 | 0.854167 | 0.891228 | 0 |
| Pre-import v2 | 0.785714 | 0.964286 | 1.000000 | 0.877976 | 0.909086 | 0 |
| Post-import v1 | 0.392857 | 0.714286 | 0.821429 | 0.560714 | 0.626207 | 5 |
| Post-import v2 | 0.464286 | 0.857143 | 1.000000 | 0.676786 | 0.758083 | 0 |

V2 resolves evidence-equivalence failures but does not erase the independent
early-ranking deficit caused by corpus expansion. The result validates the
dataset update and preserves the ranking blocker as a separate concern.
