# Task 25B-R3-DEV-R2 Stratified Dataset v3

Generated: 2026-07-12T13:04:32.172987+00:00

```json
{
  "generated_at": "2026-07-12T12:22:11.648047+00:00",
  "dataset_version": "task25b_r3_dev_r2_zh_v3",
  "case_count": 240,
  "splits": {
    "train": 120,
    "dev": 60,
    "test_v3": 60
  },
  "dataset_sha256": "95053c0f26d783affe522ad9ad2b73af985f81e83b144c2913f7ebf088f97070",
  "test_v3_coverage": {
    "total": 60,
    "model_cases": 12,
    "alarm_cases": 12,
    "vector_heavy": 20,
    "no_answer": 10,
    "multi_relevant": 18,
    "single_relevant": 32,
    "safety": 8,
    "communication": 9,
    "storage": 8,
    "smartlogger": 5,
    "inverter": 12,
    "hard_negative": 10
  },
  "expert_verified": false,
  "test_v3_frozen": false,
  "stratified": true,
  "source": "current approved Chinese Pilot chunks"
}
```

Pre-freeze drafts (1,200 cases) are retained only as invalid audit history after stratification and query-grounding rebuilds. The current v3 dataset remains unfrozen because Canary did not pass.
