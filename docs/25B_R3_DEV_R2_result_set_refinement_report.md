# Task 25B-R3-DEV-R2 Result Set Refinement

Generated: 2026-07-12T13:04:32.170989+00:00

- Candidate generation retains raw Top-10 for evaluation and audit.
- The user-facing result set is independently refined by section collapse, near-duplicate collapse, a two-per-document cap, score cutoff and dynamic 1-5 result sizing.
- API diagnostics expose raw/surfaced counts, cutoff reason, collapsed groups, and section/document diversity.
- Benchmark expected labels are never returned by ordinary retrieval APIs.
