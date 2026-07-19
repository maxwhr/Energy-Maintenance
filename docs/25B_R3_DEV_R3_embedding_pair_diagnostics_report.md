# Task 25B-R3-DEV-R3 Embedding Pair Diagnostics

- Pairs: 40 source-grounded train/dev candidates; test_v3 used: `False`.
- Model/dimension: `text-embedding-v4` / 1024.
- Raw positive similarity: 0.510375.
- Semantic positive similarity: 0.558528.
- Hard-negative similarity: 0.504429.
- Raw positive margin: 0.005946.
- Semantic positive margin: 0.054099.
- Primary diagnosis: `RAW_CHUNK_REPRESENTATION_DILUTION`.

The reproducible semantic-minus-raw lift (0.048153) and positive-margin lift diagnose raw Chunk representation dilution. These diagnostic thresholds are not acceptance thresholds and did not use Benchmark expected labels or export vectors.
