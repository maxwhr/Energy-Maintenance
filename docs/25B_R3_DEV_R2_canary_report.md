# Task 25B-R3-DEV-R2 Canary

Generated: 2026-07-12T13:04:32.172987+00:00

```json
{
  "status": "CANARY_FAILED",
  "cases": 24,
  "checks": {
    "label_validity": true,
    "coverage": true,
    "no_leakage": true,
    "keyword_external_zero": true,
    "keyword_recall_at_5": false,
    "vector_recall_at_5": false,
    "citation_validity": true,
    "keyword_p95": false,
    "vector_hybrid_adaptive_p95": false,
    "error_zero": true,
    "adaptive_vector_heavy_route": true,
    "mode_not_all_identical": true,
    "vector_heavy_gain": false
  },
  "vector_heavy": {
    "cases": 6,
    "keyword_recall_at_5": 0.0,
    "vector_recall_at_5": 0.055556,
    "adaptive_recall_at_5": 0.0,
    "keyword_ndcg": 0.0,
    "adaptive_ndcg": 0.0,
    "adaptive_mrr": 0.0,
    "vector_candidate_recall_at_50": 0.055556,
    "adaptive_routes": {
      "hybrid": 4,
      "keyword": 2
    },
    "relative_recall_gain": 0.0,
    "relative_ndcg_gain": 0.0
  }
}
```

Canary failure strictly prohibits freezing test_v3 and running the one permitted formal v3 quality gate.

<!-- TASK25B_R3_DEV_R3 -->
## Task 25B-R3-DEV-R3 semantic recall diagnosis

- R2 Canary remains `CANARY_FAILED` and its artifacts are preserved read-only.
- Raw Chunk representation dilution was diagnosed with train/dev-only embedding pairs; DashVector filtering and mapping were not the root cause.
- An isolated `pilot_r3_semantic` A/B partition was created with 416 source-only anchors. `pilot_r2`, the default partition, and the original 1,262 vectors were not changed.
- The independent Canary failed: semantic Candidate Recall@50 = 0.444444, below 0.90. `test_v3_1` was not created or frozen and no formal quality run or full reindex occurred.
- `expert_verified=false`; no package, Git commit, or LoongArch physical verification occurred.
