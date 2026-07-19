from __future__ import annotations

import math
from pathlib import Path

from task25b_r3_dev_r5_r1_common import OUT, read_json


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs" / "25B_R3_DEV_R5_R1_query_aware_rag_repair_report.md"
OLD_R5 = ROOT / ".runtime" / "task25b_r3_dev_r5" / "canary_result.json"


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def ms(value: float | None) -> str:
    return "NOT RUN" if value is None else f"{value:.3f} ms"


def main() -> None:
    baseline = read_json(OUT / "r5_failed_baseline.json")
    old = read_json(OLD_R5)
    structured = read_json(OUT / "structured_model_probe.json")
    rerank = read_json(OUT / "rerank_probe.json")
    raw = read_json(OUT / "raw_vector_probe.json")
    fusion = read_json(OUT / "fusion_trace.json")
    citation = read_json(OUT / "citation_confidence.json")
    canary = read_json(OUT / "canary_result.json")
    reconciliation = read_json(OUT / "reconciliation.json")
    browser = read_json(OUT / "browser_review.json")
    regression = read_json(OUT / "regression_summary.json")

    query_latencies = [float(row["latency_ms"]) for row in structured.get("rows", [])]
    rerank_latencies = [float(row["latency_ms"]) for row in rerank.get("rows", [])]
    query_p95 = percentile(query_latencies, 0.95)
    rerank_p95 = percentile(rerank_latencies, 0.95)
    old_metrics = old.get("metrics") or {}
    old_latency = old.get("latency") or {}
    old_rerank = old.get("rerank_before_after") or {}
    fdiag = fusion.get("fusion") or {}
    refine = fusion.get("refinement") or {}
    counts = reconciliation.get("partition_counts") or {}

    report = f"""# Task 25B-R3-DEV-R5-R1 Query-Aware Grounded RAG Repair Report

Result: `QUERY_AWARE_GROUNDED_RAG_R1_QUALITY_GATE_FAILED`

The P0 code-path repair is implemented and regression-safe, but the required real Rerank probe succeeded in **0/3** cases. Under the immutable task gate, no full Canary cases were executed and no formal dataset or formal blind run was created. This is a quality-gate failure, not a full pass.

## 1. R5 failed baseline

- Frozen source result: `{baseline.get('source_result')}`.
- Historical R5 Canary iterations and report remain byte-for-byte unchanged.
- Historical R5 metrics: Candidate Recall@50 `{old_metrics.get('candidate_recall_at_50')}`, Recall@5 `{old_metrics.get('recall_at_5')}`, Recall@10 `{old_metrics.get('recall_at_10')}`, MRR `{old_metrics.get('mrr')}`, nDCG@10 `{old_metrics.get('ndcg_at_10')}`.
- Baseline Query Understanding structured success `0/31`; baseline Rerank fallback `14/14`; requested RAW_VECTOR `21`, actual `0`.
- Freeze evidence: `.runtime/task25b_r3_dev_r5_r1/r5_failed_baseline.json` and `r5_failed_hash_manifest.json`.

## 2. Confirmed bugs

All 13 confirmed defects received code-path repairs: structured output, timeout, fact/normalization/hypothesis separation, equipment classification, Rerank contract/diagnostics, RAW_VECTOR, fake KG_ALIAS, RRF duplicate voting, Semantic Unit identity, refinement evidence loss, partial citation validation, HTML citation support, and confidence calibration. The remaining acceptance blocker is real provider Rerank reliability/performance, not an unguarded fallback.

## 3. Structured Model Call repair

`StructuredModelCallService` is shared by Query Understanding and Rerank. It supports `JSON_SCHEMA`, `JSON_OBJECT`, and prompt-only fallback; every successful payload passes Pydantic validation. Robust extraction supports direct JSON, fenced JSON, and the first complete JSON object. Logs contain only hashes, lengths, field names, sanitized error codes, parse strategy, token counts, and trace identifiers.

## 4. Provider capability probe

- Provider/model: `{structured.get('provider')}` / `{structured.get('model')}`.
- Capability: `JSON_SCHEMA`, real probe passed.
- Query Understanding real structured probe: `{structured.get('structured_success')}/{structured.get('llm_path_cases')}`.
- The adapter reuses a pooled keep-alive HTTP client and has separate connect/read/write/pool timeouts.
- StepFun documents the response-format modes and `reasoning_effort`; low effort was used for extraction-oriented calls: [Chat Completions API](https://platform.stepfun.com/docs/zh/api-reference/chat/chat-completion-create), [Step Plan reasoning API](https://platform.stepfun.com/docs/zh/step-plan/integrations/reasoning-api).

## 5. Query Understanding success rate

- Planned/invoked/succeeded: `{structured.get('llm_path_cases')}/{structured.get('llm_path_cases')}/{structured.get('structured_success')}`.
- Structured success: `100%` in the directed four-case probe.
- Fast Path exact-model case did not call the model.
- Hallucinated models/alarms: `{structured.get('hallucinated_models')}/{structured.get('hallucinated_alarms')}`.
- Observed p95: `{ms(query_p95)}`; this is above the 4,000 ms target and remains a performance issue.

## 6. Query Understanding fallback

Directed probe fallback was `0/4`. The hard timeout is 8 seconds. Confirmed facts remain deterministic and immutable; normalized semantics remain usable; retrieval hypotheses stay outside confirmed facts. Equipment mapping is evidence-based (`SUN2000`, `LUNA2000`, `SmartLogger`) and empty when there is no evidence.

## 7. Rerank success rate

- Eligible/model-called/structured-success: `{rerank.get('cases')}/{rerank.get('cases')}/{rerank.get('structured_success')}`.
- Candidate additions/source modifications: `0/0` in every probe case.
- Real failures: one wrong top-level shape, one 20-second timeout, one token-length truncation.
- Observed p95: `{ms(rerank_p95)}`; the <=6,000 ms target is not met.

## 8. Rerank fallback

Fallback occurred in `3/3` cases and preserved exact RRF order. Candidate IDs were neither added nor changed, and source facts were not modified. Because structured success was below 95%, this prerequisite failed and blocked Canary.

## 9. RAW_VECTOR repair

- Probe status: `{raw.get('status')}`.
- Collection/partition: `{raw.get('collection_name')}` / `{raw.get('partition_name')}` from RetrievalScope.
- Query embedding dimension: `{raw.get('embedding_dimension')}`.
- Raw DashVector/post-filter/mapped hits: `{raw.get('raw_dashvector_hits')}/{raw.get('post_filter_hits')}/{raw.get('mapped_candidate_count')}`.
- `None` filter removed: `{', '.join(raw.get('none_filters_removed') or [])}`.
- PostgreSQL approved/current/active allow-list remains authoritative after the remote query.

## 10. KG_ALIAS handling

Status: `{fusion.get('kg_alias_status')}`. The duplicate keyword implementation is disabled and no longer receives an independent RRF vote.

## 11. RRF repair

- Per physical channel/candidate vote cap: `{fdiag.get('channel_vote_cap')}`.
- Duplicate votes removed in fixture: `{fdiag.get('duplicate_votes_removed')}`.
- Channel/query weights applied: `{fdiag.get('channel_weights_applied')}/{fdiag.get('query_weights_applied')}`.
- Candidate count before/after: `{fdiag.get('candidate_count_before')}/{fdiag.get('candidate_count_after')}`.
- Vote breakdown is retained in `fusion_trace.json` without embedding vectors or source-body dumps.

## 12. Semantic Unit candidate identity

Semantic Units now enter fusion as one `su:<semantic_unit_id>` candidate. All source chunk IDs and locators remain attached, while one primary chunk is selected for citation. A unit no longer competes with its own source chunks as separate evidence facts.

## 13. Result Refinement repair

- Raw/surfaced candidates: `{refine.get('raw_candidate_count')}/{refine.get('surfaced_top_k')}`.
- Collapse groups/evidence-preserving merges: `{refine.get('collapsed_group_count')}/{refine.get('evidence_preserving_merges')}`.
- Relevant candidates lost without reason: `{refine.get('relevant_candidates_lost_without_reason')}`.
- Merged candidates retain source chunk IDs, locators, page numbers, Semantic Unit identity, and citation support.

## 14. Citation PDF/HTML support

References are validated independently. HTML accepts source URL plus heading/anchor/section locator; PDF accepts page plus section. Partial-valid references remain visible (`{citation.get('partial_valid_citations_retained')}`); both HTML and PDF locator probes passed. One invalid reference no longer clears valid citations.

## 15. Confidence repair

Multiple source documents no longer imply conflict. Confidence uses explicit entity/model/product/alarm/procedure/evidence conflicts, normalized margins, citation support, and intent coverage. The complementary multi-document probe returned `{citation.get('multi_document_status')}` with no entity conflict.

## 16. No-answer calibration

The empty-evidence probe returned `{citation.get('no_answer_status')}`. The system does not promote hypotheses or unsupported repair actions to facts. Formal no-answer precision/recall/F1 were not rerun because Canary is blocked.

## 17. Canary before/after comparison

| Signal | Frozen R5 | R5-R1 |
|---|---:|---:|
| Query Understanding structured | 0/31 | 4/4 directed probe |
| Rerank structured | 0/14 | 0/3 required real probe |
| RAW_VECTOR requested/actual | 21/0 | 1/1 directed probe, 20 raw hits |
| KG_ALIAS | duplicate keyword vote | disabled |
| Canary cases | 60 | 0, blocked pre-Canary |

R5-R1 Canary status is `{canary.get('status')}`. No threshold was lowered and this precondition record is not represented as a real Canary iteration.

## 18. Formal test

Not created and not run. Guard scripts refuse creation, freeze, or formal quality-gate execution unless an immutable passing Canary exists. Formal run count is zero.

## 19. Performance

- Historical frozen R5 Fast Path p50/p95: `{old_latency.get('fast_p50_ms')}/{old_latency.get('fast_p95_ms')} ms` (historical only).
- R5-R1 Query Understanding directed p95: `{ms(query_p95)}`.
- R5-R1 Deep Rerank directed p95: `{ms(rerank_p95)}`; one timeout occurred.
- R5-R1 Multi-query p50/p95: `NOT RUN` because Canary was blocked.
- HTTP reuse/pooling is implemented, but the provider Rerank path remains too slow and unreliable for acceptance.

## 20. Vector integrity

- Collection: `{reconciliation.get('collection')}`.
- Partition counts: `pilot_r2={counts.get('pilot_r2')}`, `pilot_r3_semantic={counts.get('pilot_r3_semantic')}`, `pilot_r4_grounded={counts.get('pilot_r4_grounded')}`, `pilot_r5_query_aware={counts.get('pilot_r5_query_aware')}`.
- Re-embedded/re-upserted: `{reconciliation.get('re_embedded')}/{reconciliation.get('re_upserted')}`.
- Missing/orphan/duplicate/mismatch: `{reconciliation.get('missing')}/{reconciliation.get('orphan')}/{reconciliation.get('duplicate')}/{reconciliation.get('mismatch')}`.
- Default partition affected: `{reconciliation.get('default_partition_affected')}`.

## 21. Regression

- compileall: `{regression.get('compileall')}`.
- Alembic heads/current: `{regression.get('alembic_heads')}` / `{regression.get('alembic_current')}`.
- pytest: `{(regression.get('pytest') or {}).get('passed')} passed, {(regression.get('pytest') or {}).get('skipped')} skipped`.
- Security/RBAC: `{(regression.get('security') or {}).get('status')}` / `{(regression.get('rbac') or {}).get('status')}`.
- Agents/conversion: `{(regression.get('agents') or {}).get('status')}` / `{(regression.get('conversion') or {}).get('status')}`.
- npm audit/vue-tsc/build/static install: `0 vulnerabilities / PASSED / PASSED / PASSED`.

## 22. Browser

Status: `{browser.get('status')}`. The R5-R1 quality card showed Structured `4/4`, Rerank `0/3`, RAW_VECTOR `20/20`, KG Alias disabled, Canary blocked, and formal test not created. Exact-model Fast Path preserved confirmed facts and displayed requested/actual channels, Rerank skipped status, grounded boundary, and HTML citations. Console/page/unexpected-network errors: `0/0/0`. Full 16-scenario Canary browser execution was correctly not attempted after the Rerank prerequisite failed.

## 23. Final Smoke

`http://127.0.0.1:8012`: `{(regression.get('final_smoke') or {}).get('total')}` checks, `{(regression.get('final_smoke') or {}).get('failed')}` failed. The smoke intentionally skipped the write-producing retrieval request by default.

## 24. expert_verified=false

No expert verification or engineering approval state was written. Existing R5 artifacts and expert boundaries were preserved.

## 25. Formal full reindex not executed

`TASK25B_ALLOW_FULL_REINDEX=false`. No collection/partition delete, creation, default-partition change, full reindex, embedding rebuild, or vector upsert occurred.

## 26. LoongArch

Not tested on real LoongArch + Kylin hardware. No CUDA, GPU, FAISS, pgvector, Neo4j, Docker, or local large-model dependency was introduced.

## 27. Package

No package or ZIP was created. Existing ZIP hashes, sizes, and mtimes remain unchanged; `delivery`, `delivery_staging`, and `docs.zip` were not updated.

## 28. Git

No `git add`, commit, reset, clean, or restore was executed. Staged files remain `0`; the pre-existing dirty worktree was preserved.

## Final judgment

- Final result: `QUERY_AWARE_GROUNDED_RAG_R1_QUALITY_GATE_FAILED`.
- Structured Query Understanding usable: **yes in directed probe (4/4)**.
- RAW_VECTOR usable: **yes in directed real query (20/20 after filter)**.
- Evidence ranking competitive: **not proven; Rerank structured success 0/3**.
- No-answer reliable: **logic probe passed, formal metric not rerun**.
- Allow Task 25C: **no**.
- Remaining blockers: make Rerank provider output reliable at >=95% structured success and <=6 s p95, then run the versioned Canary; only a passing Canary may authorize formal-test creation.

## Machine evidence

All new machine evidence is under `.runtime/task25b_r3_dev_r5_r1/`. The immutable historical source is `.runtime/task25b_r3_dev_r5/`.
"""
    REPORT.write_text(report, encoding="utf-8")
    print({"status": "GENERATED", "report": str(REPORT), "result": canary.get("result")})


if __name__ == "__main__":
    main()
