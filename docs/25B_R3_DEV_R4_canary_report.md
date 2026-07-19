# Task 25B-R3-DEV-R4 Grounded Canary Report

## Final result

`CANARY_FAILED` after the maximum two Train/Dev iterations. The result is `DEVELOPMENT_ENGINEERING_VECTOR_RECALL_NOT_PROVEN`; thresholds were not reduced and further tuning stopped.

The fixed Canary contains 40 cases: 25 vector-heavy plus 5 model, 5 alarm, and 5 no-answer cases; safety and communication coverage each exceed four. All vector-heavy cases are `GROUNDED_STRONG`, with zero lexical leakage.

| Metric (vector-heavy) | Iteration 1 | Iteration 2 | Required |
|---|---:|---:|---:|
| Candidate Recall@50 | 0.48 | 0.80 | >=0.90 |
| Grounded semantic Recall@5 | 0.08 | 0.44 | >=0.80 |
| Adaptive grounded Recall@5 | 0.20 | 0.40 | >=0.85 |
| Adaptive MRR | 0.084498 | 0.288050 | >=0.75 |
| Adaptive nDCG@10 | 0.122817 | 0.339479 | >=0.80 |
| Relative Recall@5 gain over keyword | 0.00 | 0.20 | >=0.10 or nDCG gain >=0.08 |
| Warm p95 | 8437.560 ms | 3474.794 ms | <=3500 ms |

Iteration 2 passed relative gain, warm p95, actual-route, original-chunk citation mapping, leakage=0, error=0, and partition integrity checks. It still failed all absolute semantic recall/ranking thresholds.

The single permitted tuning changed only general Train/Dev query focus representation, intent routing priority, typed consistency, and type-diverse candidate retention. It did not change case labels, source facts, test data, benchmark queries in anchors, or case-ID-specific behavior.

No formal v4 dataset was created or frozen and no formal run occurred. Evidence: `.runtime/task25b_r3_dev_r4/canary_iteration_1.json`, `canary_iteration_2.json`, `canary_result.json`, and `dev_tuning.json`.

