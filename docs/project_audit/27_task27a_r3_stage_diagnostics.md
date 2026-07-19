# Task 27A-R3 Failure Stage Diagnostics

**Mode:** keyword-only, read-only PostgreSQL  
**Frozen dataset SHA-256:** `9d2400a26f2a50ea3894b46ee2d5e2f88392ee1a539695a9467490e6d9ff20b0`  
**Production QA count:** 2598 before / 2598 after

## 1. Method

`diagnose_task27a_r3_failure_stages.py` captured the existing production pipeline without passing labels to retrieval or answer generation. Expected IDs were used only after each request completed to locate the labelled evidence in the captured stages.

The physical implementation loads/hydrates the immutable 621-chunk scope before keyword ranking. For reporting clarity, the lifecycle is represented as:

```text
Scope + hydration
-> per-variant keyword candidates
-> multi-query identity budget
-> RRF fusion
-> pre-rerank hard guard
-> deterministic rerank
-> presentation Top 5/refinement
-> citation validation and answer evidence
```

No real provider, vector channel, persistence, migration, or write operation was used.

## 2. Stage Summary Before R3 Ranking/Answer Changes

| Case | Initial best | Fused | Guard | Rerank | Final | Answer selected | Main loss |
|---|---:|---:|---:|---:|---:|---|---|
| HUAWEI-ALARM-001 | 1 | 1 | 1 | 1 | 1 | yes | Answer point selection |
| HUAWEI-INSULATION-002 | 3 | 3 | 3 | 3 | 3 | yes | Calculation sentence selection |
| HUAWEI-COMM-003 | 1 | 1 | 1 | 6 | - | no | Deterministic ranking |
| HUAWEI-TEMP-002 | 1 | 2 | 2 | 1 | 1 | yes | Strict phrase normalization |
| HUAWEI-TEMP-003 | 3 | 3 | 3 | 1 | 1 | yes | Strict phrase normalization |
| HUAWEI-GRID-001 | 1 | 1 | 1 | 1 | 1 | yes | Excerpt boundary |
| HUAWEI-DC-002 | 1 | 1 | 1 | 22 | - | no | Deterministic ranking |
| HUAWEI-SAFETY-001 | 5 | 6 | 6 | 11 | - | no | Generic safety evidence outranks narrow action evidence |
| HUAWEI-SAFETY-002 | 3 | 3 | 3 | 12 | - | no | Generic shutdown evidence outranks dual-side verification |

All nine expected chunks are present in the formal scope. None is removed by the hard guard. Increasing the candidate pool cannot solve the four principal ranking failures because every expected chunk already enters fusion near the top.

## 3. Ranking/Citation Cases

### HUAWEI-COMM-003

- Expected evidence: EDOC1100273863, section `64 “通信断链保护`, page 124.
- Expected content contains both `RS485-2` and the `通信断链保护时间` parameter row.
- Initial/fused/guard rank: 1/1/1.
- Rerank: 6; query lexical support 1.0; requested-information coverage 0.5; intent match 0.5; final score 0.766667.
- Higher generic passages receive full `PROCEDURE + CONFIGURATION` coverage even when they do not contain the RS485-2 parameter row. The requested-information classifier is too permissive for generic parameter tables and does not reward compound phrase proximity.
- Required layer: phrase/proximity, rare token, and configuration-intent ranking.

### HUAWEI-DC-002

- Expected evidence: EDOC1100273863, section `1 “MPPT多峰扫`, page 118.
- Expected content directly states that obvious string shading should enable periodic global MPPT scanning to find the maximum power value.
- Initial/fused/guard rank: 1/1/1.
- Rerank: 22; query lexical support 1.0; requested-information coverage 0; intent match 0.714286; final score 0.656310.
- Generic string installation and MPPT passages receive false full CAUSE support, while the exact `多峰扫描 + 遮挡 + 全局MPPT + 功率最大值` row is marked non-supporting.
- Required layer: cause-intent support terms and compound phrase/proximity ranking.

### HUAWEI-SAFETY-001

- Expected evidence: EDOC1100059933, `1.1 人身安全`, page 9.
- It explicitly prohibits energized cable installation/removal and requires insulated tools and PPE.
- Initial/fused/guard rank: 5/6/6; rerank rank 11; lexical 0.64; safety coverage 1.0; final score 0.740990.
- Generic lifting, site selection, and PPE passages are incorrectly treated as equally direct safety answers.
- A byte-equivalent copy exists in EDOC1100253089. The frozen label points to the installation guide, so a generic document-purpose match (`安装/拆装` -> installation guide) is preferable to arbitrary duplicate selection.
- Required layer: high-risk action phrases, rare-token proximity, safety intent, and document-purpose match.

### HUAWEI-SAFETY-002

- Expected evidence: EDOC1100270192, page 81.
- It contains the complete sequence: disconnect AC, measure each DC string current, measure AC terminal-to-ground voltage, disconnect DC, then wait 15 minutes.
- Initial/fused/guard rank: 3/3/3; rerank rank 12; lexical 0.84375; requested-information coverage 0.5; intent match 1.0; final score 0.755492.
- General DC safety and shutdown passages outrank the narrower dual-side verification procedure because `测量 + 直流电流 + 交流端子排 + 对地电压 + 15min` is not scored as a compound verification bundle.
- Required layer: verification-intent phrase coverage and rare numeric-unit protection restricted to maintenance context.

## 4. Answer Coverage Cases

### HUAWEI-ALARM-001

The labelled alarm 103 row is rank 1 and selected. The current 320-character excerpt starts near one matching term and does not reliably preserve the full table row: alarm meaning, open-circuit cause, and series-configuration action. This is an answer sentence/table-row selection defect.

### HUAWEI-INSULATION-002

The labelled location-calculation chunk is final rank 3 and selected. The answer chooses the general insulation workflow before the component-count/percentage/suspected-position relationship. Calculation and quantity terms need a generic sentence-window preference.

### HUAWEI-TEMP-002

The labelled fan-maintenance chunk is final rank 1. The answer says `清理风扇上的异物`, which is semantically equivalent to the frozen point `清理异物`. This is an evaluator normalization sensitivity; action and object are both present.

### HUAWEI-TEMP-003

The labelled installation chunk is final rank 1 and the answer includes direction-specific clearance values and says they provide installation/heat-dissipation space. The strict label expects the literal `安装距离`. This is another generic normalization case, provided the numeric distances remain present.

### HUAWEI-GRID-001

The labelled alarm table is the only final reference. The answer preserves voltage and AC breaker/line checks but its selected window omits the source-supported escalation to the local power operator. A query-aware multi-sentence/table-row window is required.

## 5. Diagnosis Decision

- Scope/SQL recall defect: no.
- Candidate depth defect: no.
- Hard-guard removal defect: no.
- Deterministic ranking defect: yes, four cases.
- Answer/excerpt selection defect: yes, at least three cases.
- Generic evaluator normalization defect: yes, two cases.
- Missing knowledge: no; all labelled chunks exist in the 621-chunk formal scope.
- Provider/model defect: no provider was called.

The first production experiment may therefore add general phrase/proximity and rare-token scoring. Candidate pool depth remains unchanged. Subsequent intent and answer changes must be evaluated separately against the same hash.

## 6. Post-fix Stage Result

The experiments followed the diagnosed layers rather than expanding scope or candidate depth. The broad first phrase experiment was rejected after it regressed one model case. Phrase scoring was retained only for context-sensitive configuration, cause, safety, verification, prerequisite, and calculation intents. Intent term computation was then reused per query to remove the first implementation's latency inflation.

| Case | Pre-change deterministic/final rank | Final rank | Answer selected | Strict coverage | Result |
|---|---|---:|---|---:|---|
| HUAWEI-ALARM-001 | 1 / 1 | 1 | yes | 1.0 | fixed |
| HUAWEI-INSULATION-002 | 3 / 3 | 3 | yes | 1.0 | fixed |
| HUAWEI-COMM-003 | 6 / outside Top 5 | 1 | yes | 1.0 | fixed |
| HUAWEI-TEMP-002 | 1 / 1 | 1 | yes | 1.0 | fixed |
| HUAWEI-TEMP-003 | 1 / 1 | 1 | yes | 1.0 | fixed |
| HUAWEI-GRID-001 | 1 / 1 | 1 | yes | 1.0 | fixed |
| HUAWEI-DC-002 | 22 / outside Top 5 | 1 | yes | 1.0 | fixed |
| HUAWEI-SAFETY-001 | 11 / outside Top 5 | 1 | yes | 1.0 | fixed |
| HUAWEI-SAFETY-002 | 12 / outside Top 5 | 2 | yes | 1.0 | fixed |

Final strict metrics are Recall@1 `0.750000`, Recall@3 `0.964286`, Recall@5 `1.000000`, MRR `0.854167`, nDCG@5 `0.891228`, citation support `1.000000`, and required answer-point coverage `1.000000`. No scope, citation-validity, manufacturer, safety, abstention, pending/archived, or persistence regression was detected. The final R3 read-only evaluation again observed 2598 QA records before and after.
