# Task 28A-R3I Product Closure And Ranking Deferral

> Historical Blocked Attempt: this closure report records the first R3I run
> that was blocked by the unresolved merge. It is intentionally preserved and
> will not be overwritten by the authorized rerun report.

## Product Functional Status

`TASK28A_R3I_BLOCKED_BY_PREEXISTING_UNRESOLVED_MERGE`

The formal corpus and Task 29B static login entry passed the read-only checks
available to this task. Product closure did not pass because the current
working tree cannot compile, build, start a new backend, or execute the
isolated knowledge/auth workflow while eight merge paths remain unresolved.

## Engineering Ranking Status

`ENGINEERING_EARLY_RANKING_RESEARCH_DEFERRED`

The R3G product-safe evidence remains the appropriate baseline for a future
fresh run: Top-5 evidence, citations, required-point coverage, scope, safety,
and abstention are the product gates. Recall@1/3, MRR, and nDCG@5 remain
engineering research objectives and must not be optimized against consumed
Holdout labels.

## Historical R3H Status

`RANKING_OVERFIT_DETECTED`

R3H established real score-provenance and monotonic-rerank defects, but its
one-shot independent Holdout and frozen no-regression gates failed. The current
R3H default therefore cannot be declared product-safe solely from historical
evidence. No new Holdout run or post-Holdout tuning occurred in R3I.

## Safe Claims

- Formal PostgreSQL data and all protected counts matched the required
  read-only baseline.
- The 10 imported Huawei SUN2000 documents and 937 chunks remain parsed,
  approved, active, and source-traceable; imported Sungrow contamination is 0.
- The Task 29B public and authentication pages remain available from the
  already-running static bundle.
- Frozen v1/v2 files are unchanged and production code contains no fixture
  literal leakage.
- Formal residue inventory and a no-execution cleanup plan are available.

## Claims Not Permitted

- Task 28A product functional acceptance passed.
- Current-source backend compile/build passed.
- Current-source browser/API/RAG workflow passed.
- R3G safe rollback is active in production.
- Isolated upload/parser/review/retrieval/archive/auth acceptance passed.
- Formal cleanup was executed.

## Required Next Action

Resolve the pre-existing merge in a separately authorized task with explicit
choices for Provider, knowledge service, retrieval API/service, and Task 29B
login/auth sources. Do not use `git reset`, `git restore`, or a whole-tree side
selection. After resolution, rerun Task 28A-R3I from a cleanly recorded source
baseline and keep the consumed R3G/R3H Holdouts frozen.
