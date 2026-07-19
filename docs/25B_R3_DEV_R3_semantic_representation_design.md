# Task 25B-R3-DEV-R3 Semantic Representation Design

`MaintenanceSemanticRepresentationService` constructs a versioned, reproducible source-only representation from the current Chunk, its document metadata, structured alarm metadata, and its source locator. Missing causes remain empty; no LLM fills missing facts.

- Version: `task25b_r3_dev_r3_semantic_v1`.
- Source chunks in the isolated Canary design: 121.
- Anchor count: 416.
- Anchor types: ACTION, COMPONENT, FULL_SEMANTIC, SAFETY, SYMPTOM.
- Benchmark query used: `False`; test_v3 used: `False`.
- Each anchor keeps source Chunk ID, locator, language, approval/current metadata, representation hash/version, and stable `source_chunk_uuid + anchor_type` vector ID.

The semantic query representation retains the original query and traceable normalized terms. It does not inject document titles, expected labels, models, or alarm codes that were not expressed by the user.
