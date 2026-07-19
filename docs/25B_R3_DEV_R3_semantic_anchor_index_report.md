# Task 25B-R3-DEV-R3 Semantic Anchor A/B Index

- Collection: `energy_kn_te_v4_1024_v1`.
- Raw partition retained: `pilot_r2`.
- Isolated semantic partition: `pilot_r3_semantic`.
- Source chunks: 121; anchor vectors: 416.
- Index status: indexed=416, skipped=0, failed=0.
- Raw vector rewrite: `False`; full reindex: `False`; expert verified: `False`.
- Reconciliation: missing=0, orphan=0, duplicate=0, representation mismatch=0, language/status/current leakage=0/0/0.

The A/B index reconciled successfully, but it is diagnostic-only. No normal production retrieval route was enabled from this partition because the independent Canary did not pass.
