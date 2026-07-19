# Task 25B-R3-DEV-R4 Semantic Unit Index Report

## Isolated index

- Collection: `energy_kn_te_v4_1024_v1`
- Raw partition retained: `pilot_r2`
- R3 partition retained: `pilot_r3_semantic`
- R4 partition: `pilot_r4_grounded`
- Embedding: `text-embedding-v4`, dimension 1024
- Semantic units: 390
- Typed anchor vectors: 1,289
- Active: 1,289
- Failed: 0

The final remote-to-PostgreSQL reconciliation passed: remote count 1,289; missing 0; orphan 0; duplicate 0; representation-hash mismatch 0. The index does not store benchmark queries or complete vectors in artifacts.

No original chunk vector was embedded or upserted, no default partition was written, and no full reindex occurred. Evidence: `.runtime/task25b_r3_dev_r4/semantic_unit_index.json` and `semantic_unit_reconciliation.json`.

