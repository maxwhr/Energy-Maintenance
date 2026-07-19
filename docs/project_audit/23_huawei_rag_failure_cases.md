# Task 27A Huawei SUN2000 RAG Failure Cases

This report preserves the nine R2 failed cases from the frozen 30-case engineering-candidate evaluation and records their R3 resolution. No failed case was deleted, relabelled, or hard-coded away. Sections 1-9 retain the pre-R3 observations; the final R3 result is authoritative in the resolution table below.

## 1. HUAWEI-ALARM-001

- Query: 华为 SUN2000 告警代码 103 表示什么，应该先检查什么？
- Expected: chunk `70dcb0da-d4b2-40a1-9f6b-2cbe01791697`; answer points `直流输入电压高 / 开路电压 / 串联配置`.
- Signals: `huawei`, `SUN2000`, alarm `103`, fault `alarm_code_query`, intent `ALARM`, request `ALARM_MEANING`.
- Actual documents: EDOC1100022346 and EDOC1100273863.
- Actual chunks/references: labelled chunk ranked first, followed by `b52ddca4...`, `4e34fe0d...`, `f509df0e...`, and `cea70c45...`.
- Answer: cited the correct alarm table and covered `开路电压`, but the generated summary did not retain the exact `直流输入电压高` and `串联配置` points.
- Root cause: `ANSWER`; the evidence is correct, but excerpt/summary point preservation remains incomplete.
- Fix: shared query-aware excerpt selection was improved; no case-specific answer was added.
- R2 baseline: failed answer coverage; ranking and citation passed.

## 2. HUAWEI-INSULATION-002

- Query: SUN2000 绝缘阻抗故障位置百分比怎样换算到组件位置？
- Expected: chunk `091cba74-d885-43a7-8b29-e58f3281ed7e`; points `组件总数量 / 百分比 / 疑似故障位置`.
- Signals: `huawei`, `SUN2000`, fault `low_insulation_resistance`, intent/request `PROCEDURE`.
- Actual documents: EDOC1100253089 and EDOC1100270192.
- Actual chunks/references: `9b4dcb69...`, `788deb4c...`, labelled `091cba74...` at rank 3, `98f6ef8c...`, `181c9e58...`.
- Answer: explained the insulation-location workflow and displayed the percentage context, but did not preserve the component-count conversion and suspected-location wording.
- Root cause: `ANSWER`; correct evidence is present but the generated excerpt emphasizes the procedure before the calculation formula.
- Fix: shared source-diverse excerpt selection was added.
- R2 baseline: failed answer coverage; ranking and citation passed.

## 3. HUAWEI-COMM-003

- Query: FusionSolar 中 SUN2000 的 RS485-2 通信断链保护时间如何配置？
- Expected: chunk `02466942-7541-4f4c-b2ee-35ae39e0e6c8`; points `RS485-2 / 通信断链保护时间`.
- Signals: `huawei`, `SUN2000`, fault `communication_interruption`, requests `PROCEDURE / CONFIGURATION`.
- Actual documents: EDOC1100273863 only.
- Actual chunks/references: `f7d5ff99...`, `3a75aae6...`, `8d31fb51...`, `37c5523c...`, `c6ed5f4e...`; the labelled chunk was absent from top 5.
- Answer: described communication-disconnection protection time but did not ground the answer in the labelled RS485-2 configuration chunk.
- Root cause: `RANKING / CITATION / ANSWER`; general communication-protection passages outrank the narrower RS485-2 evidence.
- Fix: Chinese communication terms and query lexical support were added globally.
- R2 baseline: failed ranking, citation, and answer checks.

## 4. HUAWEI-TEMP-002

- Query: SUN2000 风扇有异常噪声时例行维护应怎样处理？
- Expected: chunk `ba3920f3-7789-4df9-b6f9-59ac00dc410e`; points `异常噪声 / 清理异物 / 更换风扇`.
- Signals: `huawei`, `SUN2000`, fault `over_temperature`.
- Actual documents: EDOC1100270192, EDOC1100253089, and EDOC1100022346.
- Actual chunks/references: labelled chunk ranked first, followed by `2f9b2e89...` and `4e34fe0d...`.
- Answer: explicitly says to clean foreign objects from the fan and replace the fan if noise remains.
- Root cause: `ANSWER/TEST_LABEL`; the evaluator requires literal `清理异物`, while the grounded answer says `清理风扇上的异物`. This is primarily normalization-sensitive scoring, not missing evidence.
- Fix: no label was weakened; the case remains visible for expert/evaluator review.
- R2 baseline: failed strict answer-point coverage; ranking and citation passed.

## 5. HUAWEI-TEMP-003

- Query: 华为 SUN2000 安装时如何预留散热空间并避免外壳高温风险？
- Expected: chunk `725c76ae-5b70-4171-9b70-e4fd4bf3a224`; points `散热空间 / 安装距离`.
- Signals: `huawei`, `SUN2000`, fault `over_temperature`, intent/request `SAFETY`.
- Actual documents: EDOC1100022346 and EDOC1100270192.
- Actual chunks/references: labelled chunk ranked first, followed by `0a60ce36...`.
- Answer: gives concrete bottom/front clearance values and says they provide installation and heat-dissipation space.
- Root cause: `ANSWER/TEST_LABEL`; the grounded numeric clearance is present, but the literal phrase `安装距离` is not emitted.
- Fix: no expected label was changed merely to pass the run.
- R2 baseline: failed strict phrase coverage; ranking, citation, and safety passed.

## 6. HUAWEI-GRID-001

- Query: 华为 SUN2000 电网电压过高或过低导致告警时如何排查？
- Expected: chunk `b52ddca4-875f-439a-9d65-4edd12d1ec5e`; points `电网电压 / 交流断路器 / 电力运营商`.
- Signals: `huawei`, `SUN2000`, fault `grid_connection_fault`, requests `CAUSE / ACTION`.
- Actual documents: EDOC1100022346.
- Actual chunks/references: the labelled chunk is the only final reference.
- Answer: covers voltage range and AC breaker/line checks, but the selected summary omits the escalation to the local power operator.
- Root cause: `ANSWER`; excerpt boundary/summary selection drops one required action from the correct source.
- Fix: shared evidence excerpting was improved but still has a boundary limitation.
- R2 baseline: failed answer coverage; ranking and citation passed.

## 7. HUAWEI-DC-002

- Query: FusionSolar 中 SUN2000 在组串遮挡场景为什么要启用 MPPT 多峰扫描？
- Expected: chunk `68272d88-13f8-45cf-bce1-174a7e24bc39`; points `遮挡 / 全局MPPT扫描 / 功率最大值`.
- Signals: `huawei`, `SUN2000`, fault `mppt_abnormal`, intent/request `CAUSE`.
- Actual documents: EDOC1100253089, EDOC1100273863, and EDOC1100270192.
- Actual chunks/references: `d6412bbb...`, `071bc6cd...`, `02466942...`, `3fd94b6a...`; the labelled chunk was absent.
- Answer: discusses general MPPT/string conditions but does not explain the multi-peak scan's search for the global power maximum.
- Root cause: `RANKING / CITATION / ANSWER`; generic MPPT and string phrases dominate the narrow multi-peak concept.
- Fix: MPPT multi-peak domain terms were added globally.
- R2 baseline: failed ranking, citation, and answer checks.

## 8. HUAWEI-SAFETY-001

- Query: 华为 SUN2000 能否带电拆装线缆，作业时需要哪些防护？
- Expected: chunk `570ac38a-e3cf-4674-ab60-6a1b68670ea6`; points `严禁带电操作 / 绝缘工具 / 防护用具`.
- Signals: `huawei`, `SUN2000`, intent/request `SAFETY`; no canonical fault type.
- Actual documents: EDOC1100253089, EDOC1100270192, and EDOC1100059933.
- Actual chunks/references: `365c19b7...`, `551088d6...`, `feee6dfb...`, `d2701d2b...`, `0915a612...`; the labelled chunk was absent.
- Answer: returns generic work-at-height/tool and cable safety passages, not the directly labelled energized-cable prohibition and PPE evidence.
- Root cause: `RANKING / CITATION / ANSWER`; high-risk action phrases do not sufficiently dominate generic safety passages.
- Fix: safety intent remains enforced and safety notes remain non-empty; evidence ranking was not hard-coded.
- R2 baseline: failed ranking, citation, and answer checks, while global safety coverage remained 1.0.

## 9. HUAWEI-SAFETY-002

- Query: SUN2000 故障检修下电后应等待多久，并如何确认交直流侧安全？
- Expected: chunk `5f881e8f-6802-43f8-a67b-a5b4fba63a62`; points `等待15min / 测量直流电流 / 测量交流端子排对地电压`.
- Signals: `huawei`, `SUN2000`, intent `SAFETY`, requests `SAFETY / VERIFICATION`.
- Actual documents: EDOC1100270192, EDOC1100059933, and EDOC1100253089.
- Actual chunks/references: `3fd94b6a...`, `8d980dce...`, `3e33ec51...`, `4905a828...`, `bd294bbb...`; the labelled chunk was absent.
- Answer: cites adjacent shutdown and DC-safety passages, including a 15-minute warning in one source, but misses the labelled dual-side measurement procedure.
- Root cause: `RANKING / CITATION / ANSWER`; the relevant procedure is a narrow chunk-boundary/verification match that generic shutdown evidence outranks.
- Fix: verification support and DC safety domain terms were added globally.
- R2 baseline: failed ranking, citation, and answer checks; safety notes remained present.

## Overall Root Cause Summary

Four failures need better narrow-evidence ranking or chunk-aware phrase matching. Five are answer coverage failures after correct evidence retrieval; two of those are also strict label-normalization mismatches. No failure is caused by cross-manufacturer contamination, fabricated references, pending/archived evidence, or provider output.

## R3 Resolution

| Case | R3 pre-change stage rank | R3 final rank | Fix layer | Fixed | Regression | Strict score | Normalized score | Final status |
|---|---|---:|---|---|---|---:|---:|---|
| HUAWEI-ALARM-001 | rerank/final 1/1 | 1 | Evidence-driven alarm table-row answer window | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-INSULATION-002 | rerank/final 3/3 | 3 | Calculation/quantity sentence selection | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-COMM-003 | rerank 6; outside Top 5 | 1 | Scoped phrase/proximity, rare token, configuration intent | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-TEMP-002 | rerank/final 1/1 | 1 | Fan action-chain answer selection; generic evaluator normalization | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-TEMP-003 | rerank/final 1/1 | 1 | Installation/clearance context selection; generic evaluator normalization | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-GRID-001 | rerank/final 1/1 | 1 | Full source-supported escalation chain | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-DC-002 | rerank 22; outside Top 5 | 1 | Cause intent, multi-peak/global-MPPT concept evidence | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-SAFETY-001 | rerank 11; outside Top 5 | 1 | Strict safety completeness and installation-purpose evidence | yes | no | 1.0 | 1.0 | passed |
| HUAWEI-SAFETY-002 | rerank 12; outside Top 5 | 2 | Verification bundle with 15min/DC-current/AC-ground-voltage terms | yes | no | 1.0 | 1.0 | passed |

The final ranks and scores come from `.runtime/task27a/keyword_evaluation_exp5_normalized.json`. Strict score is the per-case strict required-answer-point coverage and remains the pass/fail basis. Normalized score is reported in parallel only. All nine cases pass strict retrieval, citation, and answer checks; the complete 30-case run has zero failed cases and zero failure events. Scope, signal, citation validity, safety, abstention, and contamination regressions are all zero.
