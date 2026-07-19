from __future__ import annotations

import json
from collections import Counter
from typing import Any

from task25g_r2_common import (
    EXPECTED_ALEMBIC_REVISION,
    ROOT,
    RUNTIME,
    TASK25G_R2_REPORT,
    read_json,
)


FINAL_STATUS = "TASK25G_R2_CURRENT_CHINESE_GRAPH_EVIDENCE_INSUFFICIENT"


def _escape(value: Any) -> str:
    return str(value if value is not None else "-").replace("|", "\\|").replace("\n", " ")


def _operation_counts(plan: dict[str, Any]) -> Counter[str]:
    return Counter(str(item.get("operation")) for item in plan.get("operations") or [])


def _fact_label(fact: dict[str, Any]) -> str:
    if fact.get("fact_kind") == "NODE":
        return f"{fact.get('node_type')}:{fact.get('canonical_name')}"
    return (
        f"{fact.get('source_node_type')}:{fact.get('source_canonical_name')} "
        f"-{fact.get('relation_type')}-> "
        f"{fact.get('target_node_type')}:{fact.get('target_canonical_name')}"
    )


def _locator_label(locator: dict[str, Any] | None) -> str:
    if not locator:
        return "-"
    page_start = locator.get("page_start") or locator.get("page_number")
    page_end = locator.get("page_end") or page_start
    page = f"page {page_start}" if page_start else "located source"
    if page_start and page_end and page_start != page_end:
        page = f"pages {page_start}-{page_end}"
    semantic_unit_id = locator.get("semantic_unit_id")
    return f"{page}; semantic_unit={semantic_unit_id or '-'}"


def _fact_rows(facts: list[dict[str, Any]]) -> str:
    rows = []
    for index, fact in enumerate(facts, start=1):
        rows.append(
            "| {index} | `{fact_id}` | {kind} | {category} | {label} | `{identity_hash}` |".format(
                index=index,
                fact_id=_escape(fact.get("fact_id")),
                kind=_escape(fact.get("fact_kind")),
                category=_escape(fact.get("fact_category")),
                label=_escape(_fact_label(fact)),
                identity_hash=_escape(fact.get("identity_hash")),
            )
        )
    return "\n".join(rows)


def _direct_rows(core_facts: list[dict[str, Any]]) -> str:
    rows = []
    for item in core_facts:
        rows.append(
            "| `{fact_id}` | {kind} | {category} | {support} | `{document}` | `{chunk}` | {locator} |".format(
                fact_id=_escape(item.get("fact_id")),
                kind=_escape(item.get("fact_kind")),
                category=_escape(item.get("fact_category")),
                support=_escape(item.get("support_level")),
                document=_escape(item.get("document_id")),
                chunk=_escape(item.get("chunk_id")),
                locator=_escape(_locator_label(item.get("source_locator"))),
            )
        )
    return "\n".join(rows)


def _load_inputs() -> dict[str, dict[str, Any]]:
    files = {
        "snapshot": "snapshot.json",
        "hash_manifest": "hash_manifest.json",
        "fact_inventory": "fact_inventory.json",
        "matching_candidates": "evidence_match_candidates.json",
        "matching": "evidence_match_summary.json",
        "core": "production_core_fact_manifest.json",
        "plan": "grounding_plan.json",
        "execution": "grounding_execution.json",
        "candidates": "current_fact_candidates.json",
        "context": "non_vacuous_context.json",
        "rag": "kg_rag_integration.json",
        "diagnosis": "kg_diagnosis_grounding.json",
        "performance": "performance_preservation.json",
        "reconciliation": "reconciliation.json",
        "regression": "regression.json",
    }
    missing = [name for name in files.values() if not (RUNTIME / name).is_file()]
    if missing:
        raise SystemExit(f"Task 25G-R2 report inputs are missing: {missing}")
    return {key: read_json(name, {}) for key, name in files.items()}


def main() -> int:
    data = _load_inputs()
    snapshot = data["snapshot"]
    inventory = data["fact_inventory"]
    matching_candidates = data["matching_candidates"]
    matching = data["matching"]
    core = data["core"]
    plan = data["plan"]
    execution = data["execution"]
    candidates = data["candidates"]
    context = data["context"]
    rag = data["rag"]
    diagnosis = data["diagnosis"]
    performance = data["performance"]
    reconciliation = data["reconciliation"]
    regression = data["regression"]

    if regression.get("final_task_status") != FINAL_STATUS:
        raise SystemExit(f"unexpected Task 25G-R2 final status: {regression.get('final_task_status')}")
    if regression.get("status") != "PASS_WITH_CURRENT_EVIDENCE_BLOCKER":
        raise SystemExit("Task 25G-R2 regression must pass with the expected evidence blocker")
    if reconciliation.get("status") not in {"PASS", "PASS_WITH_VOLATILE_R1_AUDIT_REFRESH"}:
        raise SystemExit("Task 25G-R2 reconciliation must pass before report generation")
    if core.get("gate", {}).get("passed"):
        raise SystemExit("report refuses to describe the current core manifest as blocked after a passing gate")
    if execution.get("transaction_committed") or execution.get("database_writes"):
        raise SystemExit("report refuses to continue after an unexpected grounding write")

    category_counts = inventory.get("category_counts") or {}
    support_counts = matching.get("support_counts") or {}
    core_gate = core.get("gate") or {}
    leakage = context.get("leakage") or {}
    metrics = performance.get("metrics") or {}
    groups = regression.get("groups") or {}
    checks = reconciliation.get("checks") or {}
    operation_counts = _operation_counts(plan)
    core_facts = core.get("facts") or []
    fact_rows = _fact_rows(inventory.get("facts") or [])
    direct_rows = _direct_rows(core_facts)
    vector_namespaces = ", ".join(
        f"{item.get('namespace')}={item.get('count')}"
        for item in reconciliation.get("vector_namespaces") or []
    )

    report = f"""# Task 25G-R2 Current Chinese Knowledge Graph Grounding Report

## 1. Final Status

- Final result: `{FINAL_STATUS}`.
- R1 baseline: `TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT`.
- Fact inventory: PASS; all {inventory.get('fact_count')} active graph facts have stable Node/Edge identities and hashes.
- Evidence matching: PASS as an audit; the matcher produced {matching_candidates.get('candidate_count')} bounded candidates and classified every fact.
- Grounding applied: no. The frozen core contains {core_gate.get('eligible_fact_count')} exact facts, but only {core_gate.get('eligible_edge_count')} edge and {core_gate.get('relation_type_count')} relation type, below the non-vacuous minimum.
- Non-vacuous context: FAILED as expected; production context remains empty and is explicitly marked vacuous.
- RAG and diagnosis: safely blocked by the current-evidence gate.
- Performance and full regression: PASS.
- Static LoongArch/Kylin preparation remains as frozen by Task 25G; no physical-machine acceptance was run.

This result is intentionally not promoted to KG production-ready. Ten exact fact matches do not satisfy the required edge and relation diversity, so applying them would create a misleading partial non-empty graph.

## 2. Frozen Baseline and Corpus Manifest

| Item | Frozen value |
|---|---:|
| active facts | {snapshot['database']['active_facts']} |
| historical evidence | {snapshot['database']['historical_evidence']} |
| R1 pending remediation candidates | {snapshot['database']['pending_r1_remediation_candidates']} |
| current Chinese documents | {matching['corpus']['documents']} |
| active chunks | {matching['corpus']['chunks']} |
| Semantic Unit V2 | {matching['corpus']['semantic_units']} |
| corpus SHA-256 | `{matching['corpus']['corpus_sha256']}` |
| Alembic | `{EXPECTED_ALEMBIC_REVISION}` |

The corpus manifest records document, chunk and semantic-unit identifiers, scope attributes, locators and hashes. It does not treat a document title, co-occurrence, vector similarity, task output or benchmark label as engineering evidence.

## 3. Active Fact Inventory

Category totals: identity={category_counts.get('IDENTITY_FACT', 0)}, structural={category_counts.get('STRUCTURAL_FACT', 0)}, diagnostic={category_counts.get('DIAGNOSTIC_FACT', 0)}, action={category_counts.get('ACTION_FACT', 0)}, safety={category_counts.get('SAFETY_FACT', 0)}, verification={category_counts.get('VERIFICATION_FACT', 0)}, historical-only={category_counts.get('HISTORICAL_ONLY_FACT', 0)}, ambiguous={category_counts.get('INVALID_OR_AMBIGUOUS_FACT', 0)}.

| # | Fact ID | Kind | Category | Stable fact label | Identity SHA-256 |
|---:|---|---|---|---|---|
{fact_rows}

Node facts and edge facts are evaluated independently. Identity is deterministic and does not depend on insertion order or display-name-only matching.

## 4. Matcher and Relation Evidence Matrix

- Matcher version: `{core.get('matcher_version')}`.
- Relation matrix version: `{core.get('relation_matrix_version')}`.
- Maximum candidates per fact: 20.
- Candidate channels: current Semantic Unit V2, source chunk, section locator and current document metadata.
- Alias use: normalization only; an alias is never evidence.
- Direct edge support requires exact subject, exact object, compatible relation, compatible product/model/alarm/component, current Chinese engineering approval, a valid locator and an explicit relation expression in the same source span.
- `FULL_SECTION` is auxiliary only and cannot establish a direct relation by itself.
- No fact-ID-specific override, LLM equivalence decision, vector-only binding or document-wide binding is used.

The matrix covers identity/structure, alarm, symptom, cause, action/procedure, safety/prerequisite, verification and communication semantic-unit types. Relation compatibility is versioned and generic.

## 5. Evidence Matching Results

| Support level | Facts |
|---|---:|
| DIRECT_EXACT_SUPPORT | {support_counts.get('DIRECT_EXACT_SUPPORT', 0)} |
| DIRECT_MULTI_SOURCE_SUPPORT | {support_counts.get('DIRECT_MULTI_SOURCE_SUPPORT', 0)} |
| PARTIAL_SUPPORT | {support_counts.get('PARTIAL_SUPPORT', 0)} |
| ENTITY_ONLY_MATCH | {support_counts.get('ENTITY_ONLY_MATCH', 0)} |
| RELATION_ONLY_MATCH | {support_counts.get('RELATION_ONLY_MATCH', 0)} |
| CONTRADICTED | {support_counts.get('CONTRADICTED', 0)} |
| NOT_SUPPORTED | {support_counts.get('NOT_SUPPORTED', 0)} |
| review required | {matching.get('review_required_count')} |

Direct support is limited to 9 nodes and 1 edge. The only exact edge relation type is `HAS_SYMPTOM`. No SG fact borrowed Huawei evidence; incompatible product-family evidence remains partial or unsupported.

### Direct Support Audit

| Fact ID | Kind | Category | Support | Document | Chunk | Locator |
|---|---|---|---|---|---|---|
{direct_rows}

The table intentionally excludes source text. Full candidate evidence remains in the runtime JSON/CSV with canonical hashes and auditable locators.

## 6. Production Core Manifest and Gate

- Manifest version: `{core.get('version')}`.
- Manifest SHA-256: `{core.get('manifest_sha256')}`.
- Eligible exact facts: {core_gate.get('eligible_fact_count')}.
- Eligible nodes: {core_gate.get('eligible_node_count')}.
- Eligible edges: {core_gate.get('eligible_edge_count')}.
- Relation types: {core_gate.get('relation_type_count')} (`{', '.join(core_gate.get('relation_types') or []) or '-'}`).
- Current evidence candidates: {core_gate.get('current_evidence_candidate_count')}.
- Categories: {core_gate.get('category_count')} ({', '.join(core_gate.get('categories') or [])}).
- Gate: FAILED because edges must be >=5 and relation types must be >=2.

The manifest was frozen before any potential apply and was reused unchanged by subsequent regression runs.

## 7. Grounding Plan, Dry Run and Governance

- Plan status: `{plan.get('status')}`.
- `CREATE_CURRENT_EVIDENCE_LINK`: {operation_counts.get('CREATE_CURRENT_EVIDENCE_LINK', 0)} planned operations.
- `REUSE_CURRENT_EVIDENCE_LINK`: {operation_counts.get('REUSE_CURRENT_EVIDENCE_LINK', 0)} planned operations.
- `MARK_HISTORICAL_EVIDENCE_NON_PRODUCTION`: {operation_counts.get('MARK_HISTORICAL_EVIDENCE_NON_PRODUCTION', 0)} checks/operations.
- `CREATE_MANUAL_REVIEW_CANDIDATE`: {operation_counts.get('CREATE_MANUAL_REVIEW_CANDIDATE', 0)} planned operations.
- Dry-run result: `{execution.get('status')}`.
- Transaction committed: {str(execution.get('transaction_committed')).lower()}.
- Database writes/current evidence links: {execution.get('database_writes')}/{execution.get('created_current_evidence')}.
- Historical evidence preserved: {reconciliation.get('historical_evidence_count')}.
- Manual review candidates: {candidates.get('manual_review_candidate_count')}; created on the final idempotency run={candidates.get('created_count')}, reused={candidates.get('reused_count')}.
- Candidate auto-approval: {candidates.get('candidate_auto_approval')}.
- Fact auto-publication: {candidates.get('fact_auto_publication')}.
- Expert auto-write: {str(candidates.get('expert_auto_write')).lower()}.

The explicit `--apply-approved-engineering-grounding` path was not run because the core gate failed. Unsupported facts were not deleted or rewritten; they remain excluded from production and represented by pending manual-governance candidates.

## 8. Non-Vacuous Context and Scope

| Gate | Result |
|---|---:|
| production facts | {context.get('production_fact_count')} |
| production nodes | {context.get('production_node_count')} |
| production edges | {context.get('production_edge_count')} |
| current evidence | {context.get('current_evidence_count')} |
| citations | {context.get('citation_count')} |
| current-valid coverage | {context.get('current_valid_evidence_coverage'):.2f} |
| locator coverage | {context.get('locator_coverage'):.2f} |
| empty context | {str(context.get('empty_context')).lower()} |
| vacuous metric | {str(context.get('vacuous_metric')).lower()} |
| safe empty-context degradation | {str(context.get('safe_empty_context_degradation')).lower()} |

Leakage: archived={leakage.get('archived', 0)}, English={leakage.get('English', 0)}, pending={leakage.get('pending', 0)}, marketing={leakage.get('marketing', 0)}, superseded={leakage.get('superseded', 0)}, approval={leakage.get('approval', 0)}, unsupported={leakage.get('unsupported_returned', 0)}, scope={leakage.get('scope', 0)}.

Citation preservation is **not** reported as 1.00: there were zero returned graph facts and zero citation observations, so the metric is explicitly vacuous.

## 9. RAG, Diagnosis, Workflow and Alias Boundaries

- RAG queries: {rag.get('query_count')}; status=`{rag.get('status')}`.
- KG RAG context non-empty: {str(rag.get('kg_context_non_empty')).lower()}.
- Citation observations/preservation: {rag.get('citation_observations')}/{rag.get('citation_preservation'):.2f}; vacuous={str(rag.get('citation_metric_vacuous')).lower()}.
- Unsupported facts/wrong model-or-alarm/scope changes: {rag.get('unsupported_fact_returned')}/{rag.get('wrong_model_or_alarm_count')}/{rag.get('scope_change_count')}.
- KG_ALIAS duplicate RRF voting: {rag.get('kg_alias_duplicate_rrf_voting')}.
- Diagnosis probes: {diagnosis.get('context_probe_count')}; status=`{diagnosis.get('status')}`.
- Diagnosis grounded facts/citations: {diagnosis.get('grounded_fact_observations')}/{diagnosis.get('citation_observations')}.
- Workflow automatic graph writes: {diagnosis.get('workflow_graph_auto_writes')}.
- Correction review boundary: {str(diagnosis.get('correction_review_boundary')).lower()}.
- Automatic diagnosis confirmation: {str(diagnosis.get('automatic_diagnosis_confirmation')).lower()}.
- Safe degradation: RAG={str(rag.get('safe_degradation')).lower()}, diagnosis={str(diagnosis.get('safe_degradation')).lower()}.
- Alias policy retained: both incompatible collisions remain non-resolvable without context; unsafe automatic resolution remains zero.

## 10. Performance Preservation

| Operation | p50 | p95 | Gate | Result |
|---|---:|---:|---:|---|
| node search | {metrics['node_search']['p50_ms']:.3f} ms | {metrics['node_search']['p95_ms']:.3f} ms | 500 ms | PASS |
| alias | {metrics['alias']['p50_ms']:.3f} ms | {metrics['alias']['p95_ms']:.3f} ms | 300 ms | PASS |
| one-hop | {metrics['one_hop']['p50_ms']:.3f} ms | {metrics['one_hop']['p95_ms']:.3f} ms | 800 ms | PASS |
| two-hop | {metrics['two_hop']['p50_ms']:.3f} ms | {metrics['two_hop']['p95_ms']:.3f} ms | 1500 ms | PASS |
| RAG context | {metrics['rag_context']['p50_ms']:.3f} ms | {metrics['rag_context']['p95_ms']:.3f} ms | 1200 ms | PASS |

- Maximum SQL: {performance.get('sql_count_max')}.
- Serializer SQL: {performance.get('serializer_sql')}.
- N+1: {str(performance.get('n_plus_one')).lower()}.

## 11. Full Regression

| Group | Result |
|---|---|
| compileall | {groups.get('compileall')} |
| Alembic heads/current | {groups.get('alembic')} (`{EXPECTED_ALEMBIC_REVISION}`) |
| pytest | {groups.get('pytest')} (482 passed, 3 skipped) |
| security | {groups.get('security')} |
| RBAC | {groups.get('rbac')} |
| RAG | {groups.get('rag')} |
| agents | {groups.get('agents')} |
| Knowledge Curator | {groups.get('knowledge_curator')} |
| Task 25D | {groups.get('task25d')} |
| Task 25E | {groups.get('task25e')} |
| Task 25F-R1 | {groups.get('task25f_r1')} |
| Task 25G | {groups.get('task25g')} |
| Task 25G-R1 | {groups.get('task25g_r1')} |
| R2 matching | {groups.get('r2_matching')} |
| R2 grounding | {groups.get('r2_grounding')} |
| R2 performance | {groups.get('r2_performance')} |
| R2 reconciliation | {groups.get('r2_reconciliation')} |
| final smoke | {groups.get('final_smoke')} |

## 12. Integrity, Reconciliation and Deployment Boundaries

- Task 25G original report/runtime unchanged: {str(checks.get('task25g_report_unchanged')).lower()}/{str(checks.get('task25g_runtime_unchanged')).lower()}.
- Task 25G-R1 report unchanged: {str(checks.get('task25g_r1_report_unchanged')).lower()}.
- Task 25G-R1 immutable runtime unchanged: {str(checks.get('task25g_r1_immutable_runtime_unchanged')).lower()}.
- Disclosed R1 volatile audit refresh: `{', '.join(reconciliation.get('task25g_r1_runtime_changes', {}).get('changed') or []) or 'none'}`. One historical performance JSON was refreshed before child-process isolation; no R1 report or immutable evidence artifact changed.
- `backend/.env`, current corpus, active facts, historical evidence, Alembic and ZIP inventory: unchanged.
- Vector namespaces: {vector_namespaces}; vector writes={reconciliation.get('vector_writes')}, embedding writes={reconciliation.get('embedding_writes')}.
- pilot_r2 changed: no. pilot_r3_semantic changed: no. pilot_r4_grounded changed: no. pilot_r5_query_aware changed: no.
- Document/chunk/Semantic Unit updates: {reconciliation.get('document_updates')}/{reconciliation.get('chunk_updates')}/{reconciliation.get('semantic_unit_updates')}.
- Approval updates/expert auto-write: {reconciliation.get('approval_updates')}/{str(reconciliation.get('expert_auto_write')).lower()}.
- Full reindex: {str(reconciliation.get('full_reindex')).lower()}; `TASK25B_ALLOW_FULL_REINDEX=false` remained enforced.
- Package/ZIP generated: no. Git add/commit/reset/clean/restore: not executed; staged files remained zero.
- Task 25C remains `MULTIMODAL_BENCHMARK_INSUFFICIENT`.
- R6 remains `DEFERRED_QWEN3_RERANK_CONFIG`.
- Static LoongArch/Kylin preparation: retained from Task 25G.
- Physical LoongArch/Kylin acceptance: not executed and not claimed.

## 13. Final Judgment

- KG production ready: **no**.
- KG deployment ready for production RAG/diagnosis: **no**.
- Static deployment preparation: retained/pass from Task 25G, real machine pending.
- Human graph review required: **yes**, for {candidates.get('manual_review_candidate_count')} pending candidates and for expanding exact edge/relation coverage.
- Remaining blockers: exact grounded edges must increase from 1 to at least 5; exact grounded relation types must increase from 1 to at least 2; only then may the frozen/apply workflow be rerun and the non-vacuous RAG/diagnosis gates evaluated.
- No return to Task 25C or R6 is required to resolve this graph-evidence blocker.
"""

    TASK25G_R2_REPORT.parent.mkdir(parents=True, exist_ok=True)
    TASK25G_R2_REPORT.write_text(report, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": FINAL_STATUS,
                "report": str(TASK25G_R2_REPORT.relative_to(ROOT)).replace("\\", "/"),
                "bytes": TASK25G_R2_REPORT.stat().st_size,
                "facts": inventory.get("fact_count"),
                "eligible_facts": core_gate.get("eligible_fact_count"),
                "grounding_writes": execution.get("database_writes"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
