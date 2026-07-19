# Task 25B-R3-DEV-R3 DashVector Raw Recall Trace

- Collection/partition: `energy_kn_te_v4_1024_v1` / `pilot_r2`.
- Source-only train/dev cases: 40; test_v3 used: `False`.
- Raw Top50 expected hits: 9.
- Post-filter expected hits: 9.
- Mapping failures: 0; filter drops: 0; score-direction issues: 0; content mismatches: 0.

The equal raw/post-filter hit count shows that scope filtering and ID mapping did not remove expected results. The main failure mode was therefore raw representation recall, not post-filtering or vector-ID reconciliation.
