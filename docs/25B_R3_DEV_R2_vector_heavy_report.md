# Task 25B-R3-DEV-R2 Vector-Heavy Audit

Generated: 2026-07-12T13:04:32.172026+00:00

- Valid v2 vector-heavy cases: 0
- Unfrozen v3 test vector-heavy cases: 20
- Current train/dev Canary: CANARY_FAILED
- Vector semantic superiority is not claimed unless the independent vector-heavy gate passes.

<!-- TASK25B_R3_DEV_R3 -->
## Task 25B-R3-DEV-R3 semantic recall diagnosis

- R2 Canary remains `CANARY_FAILED` and its artifacts are preserved read-only.
- Raw Chunk representation dilution was diagnosed with train/dev-only embedding pairs; DashVector filtering and mapping were not the root cause.
- An isolated `pilot_r3_semantic` A/B partition was created with 416 source-only anchors. `pilot_r2`, the default partition, and the original 1,262 vectors were not changed.
- The independent Canary failed: semantic Candidate Recall@50 = 0.444444, below 0.90. `test_v3_1` was not created or frozen and no formal quality run or full reindex occurred.
- `expert_verified=false`; no package, Git commit, or LoongArch physical verification occurred.
