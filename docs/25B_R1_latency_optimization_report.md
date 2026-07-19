# Task 25B-R1 Latency Optimization Report

- Long-lived HTTP clients, connection pools and keep-alive are enabled.
- External concurrency is bounded at 2.
- Query embeddings use a bounded TTL cache; final ranked results, permissions and document state are not cached.
- Cold p50/p95: 443.121/3284.246 ms.
- Warm p50/p95: 533.491/1539.843 ms.
- Warm cache hit rate: 0.500000.
- Vector timeout falls back to keyword and exposes the reason.
- Warm p95 target <= 3500 ms: PASSED.
