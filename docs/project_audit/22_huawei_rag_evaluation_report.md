# Task 27A-R3 Huawei SUN2000 RAG Evaluation Report

**Evaluation mode:** keyword-only, PostgreSQL read-only  
**Overall status:** `NOT_READY`  
**Keyword engineering gate:** `PASSED`  
**Final artifact:** `.runtime/task27a/keyword_evaluation_exp5_normalized.json`

## 1. Frozen Dataset

- Dataset: `task27a_huawei_sun2000_engineering_candidate_v1`
- Version: `1.0.0`
- SHA-256: `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`
- Cases: 30, including 28 in-scope evidence cases and 2 abstention cases
- Status: `ENGINEERING_CANDIDATE`
- Human expert reviewed: **no**
- Expert gate: `BLOCKED_PENDING_HUMAN_REVIEW`

The fixture, expected documents/chunks, required points, and case count were not changed. Every evaluation recomputed the frozen hash before producing comparable metrics.

## 2. Before And After

The engineering gate continues to use the strict lexical metric. Normalized semantic coverage is reported separately and does not replace or relax the gate.

| Metric | R2 baseline | R3 final strict | Gate | Final |
|---|---:|---:|---:|---|
| Recall@1 | 0.535714 | 0.750000 | >= 0.75 | passed |
| Recall@3 | 0.821429 | 0.964286 | >= 0.90 | passed |
| Recall@5 | 0.857143 | 1.000000 | >= 0.95 | passed |
| MRR | 0.667857 | 0.854167 | >= 0.85 | passed |
| nDCG@5 | 0.715768 | 0.891228 | >= 0.85 | passed |
| Manufacturer accuracy | 1.000000 | 1.000000 | = 1.00 | passed |
| Product-family accuracy | 1.000000 | 1.000000 | = 1.00 | passed |
| Exact-model accuracy | 1.000000 | 1.000000 | >= 0.90 | passed |
| Alarm-code accuracy | 1.000000 | 1.000000 | >= 0.90 | passed |
| Citation validity | 1.000000 | 1.000000 | = 1.00 | passed |
| Citation support | 0.857143 | 1.000000 | >= 0.90 | passed |
| Required answer-point coverage | 0.794872 | 1.000000 | >= 0.85 | passed |
| Fabricated citation rate | 0.000000 | 0.000000 | = 0 | passed |
| Cross-manufacturer contamination | 0.000000 | 0.000000 | = 0 | passed |
| Out-of-scope evidence rate | 0.000000 | 0.000000 | = 0 | passed |
| Pending/archived evidence rate | 0.000000 | 0.000000 | = 0 | passed |
| Safety coverage | 1.000000 | 1.000000 | = 1.00 | passed |
| Abstention accuracy | 1.000000 | 1.000000 | >= 0.90 | passed |

Final strict failures: **0 cases / 0 events**. Final normalized required answer-point coverage: **1.000000**. Normalization produced no additional pass beyond the already-passing strict result.

Latency in the final run was P50 **1104.635 ms** and P95 **1658.421 ms**. Compared with the R2 baseline, P50 increased by 245.540 ms and P95 by 402.207 ms; both remain measured keyword-path values, not provider latency.

## 3. Controlled Experiments

| Experiment | Primary variable | R@1 | R@3 | R@5 | MRR | nDCG@5 | Answer | Failed cases | P95 ms | Decision |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Baseline | R2 state | 0.535714 | 0.821429 | 0.857143 | 0.667857 | 0.715768 | 0.794872 | 9 | 1256.214 | baseline |
| Exp 2a | broad phrase/proximity | 0.500000 | 0.857143 | 0.857143 | 0.642857 | 0.697276 | 0.807692 | 9 | 3855.688 | rejected; model regression |
| Exp 2b | scoped phrase/proximity | 0.535714 | 0.857143 | 0.892857 | 0.667857 | 0.724273 | 0.807692 | 8 | 3748.258 | retained after scoping |
| Exp 3 | intent-aware evidence | 0.607143 | 0.892857 | 0.964286 | 0.742262 | 0.797902 | 0.871795 | 6 | 5228.371 | retained, then optimized |
| Exp 4 | answer sentence/window | 0.607143 | 0.928571 | 1.000000 | 0.754167 | 0.815759 | 1.000000 | 0 | 1733.169 | retained |
| Exp 4b/4c | general ranking calibration | 0.750000 | 0.964286 | 1.000000 | 0.854167 | 0.891228 | 1.000000 | 0 | 1564.840 | retained; strict gate passed |
| Exp 5 | evaluator normalization only | 0.750000 | 0.964286 | 1.000000 | 0.854167 | 0.891228 | 1.000000 | 0 | 1658.421 | retained; strict basis unchanged |

No experiment changed candidate depth, scope membership, the frozen fixture, expected IDs, or external-provider settings. The rejected broad phrase version was narrowed before retention.

## 4. Persistence And Production Safety

The final evaluation used `persist_result=false` inside a read-only transaction. Before/after counts were identical: **372 documents, 4791 chunks, 2598 QA records**. All R3 diagnostic and evaluation runs preserved that baseline.

The isolated persistence gate remains `BLOCKED_ADMIN_ACTION_REQUIRED`: no database named with `_test` or `task27a` exists, `energy_user` lacks `CREATEDB`, and no administrator URL was available. Therefore real one-request/one-record, retry/concurrent idempotency, rollback, trace uniqueness, and Record Center visibility are not claimed.

The earlier production QA incident remains uniquely identified and `PENDING_AUTHORIZED_CLEANUP`. Cleanup was not authorized or executed. This prevents claiming that production was unchanged across the entire Task 27A period, although it was unchanged during R3.

## 5. Hybrid And Expert Status

Hybrid evaluation is `BLOCKED` and was not executed. No embedding, DashVector, vector rebuild, or real provider call was used. Expert review materials contain 30 pending rows, but no Huawei inverter-maintenance expert has reviewed or signed them.

## 6. API Regression

`check_task27a_r3_read_only_api.py` sent UTF-8 JSON through an independent temporary instance on port 8014. Alarm 103, RS485-2, MPPT multi-peak, energized-cable safety, and shutdown verification all returned real references containing the frozen expected chunk and retained every strict required answer point. Sungrow SG110CX and Huawei LUNA2000 both abstained with zero references. All seven responses had trace/request identity and `persistence_status=skipped_preview`; QA count remained 2598 before and after. No external provider was called, and the temporary instance was stopped after the run.

## 7. Decision

The keyword retrieval and answer engineering gate is **passed** and all nine frozen failures are fixed. The overall result remains **`NOT_READY`** because the required isolated PostgreSQL persistence and Record Center closed-loop acceptance has not been executed. Expert review and Hybrid are additional pending gates; only the persistence blocker is sufficient on its own to require `NOT_READY` under the R3 status rules.
