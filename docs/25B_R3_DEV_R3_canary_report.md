# Task 25B-R3-DEV-R3 Independent Train/Dev Canary

## Gate result

`CANARY_FAILED`. This is not a near-pass: the semantic Candidate Recall@50 gate failed, so the required result is `DEVELOPMENT_ENGINEERING_VECTOR_RECALL_NOT_PROVEN`.

## Vector-heavy A/B results

| Measure | Value |
| --- | ---: |
| Cases | 30 |
| Vector-heavy cases | 18 |
| Keyword Recall@5 | 0.000000 |
| Raw vector Recall@5 | 0.000000 |
| Semantic vector Recall@5 | 0.111111 |
| Adaptive semantic Recall@5 | 0.111111 |
| Semantic Candidate Recall@50 | 0.444444 |
| Adaptive semantic MRR | 0.029630 |
| Adaptive semantic nDCG@10 | 0.049270 |
| Relative Recall@5 gain | 0.111111 |
| Warm p95 (adaptive) ms | 1003.456 |

Relative semantic gain was real (+0.111111) and actual semantic routing had no fallback, leakage, or error. It is insufficient: Candidate Recall@50 was below 0.90 and quality metrics remained below the required gates. In addition, the selected vector-heavy rows included 9 `AMBIGUOUS_SECTION` labels and were not eligible to pass a grounded-vector-heavy gate. No second tuning Canary was run.

R2 remains preserved as `CANARY_FAILED`. pilot_r2 was not changed.

## Regression evidence

- Compileall: PASSED; Alembic head/current: 20260712_0012; pytest: 108 passed.
- Security/RBAC: PASSED_WITH_NOTES_0_BLOCKING / PASSED; agents and conversion: PASSED.
- Frontend build/vue-tsc/browser: PASSED / PASSED / PASSED.
- Final smoke: PASSED_23_OF_23_FAILED_0. LoongArch physical verification: NOT_RUN.
# R4 follow-up

The R3 Canary failure and Candidate Recall@50 of 0.444444 remain preserved. R4 uses a new isolated partition and a new 40-case Grounded Canary; it does not reinterpret or delete the R3 result.
