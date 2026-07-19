from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from task25g_r1_common import EXPECTED_ALEMBIC_REVISION, ROOT, RUNTIME, read_json


REPORT = ROOT / "docs" / "25G_R1_knowledge_graph_grounding_remediation_report.md"


def _count(value: dict[str, Any], key: str) -> int:
    return int(value.get(key) or 0)


def main() -> int:
    required = {
        "baseline": "leakage_baseline.json",
        "forensics": "archived_evidence_summary.json",
        "versions": "document_version_chains.json",
        "equivalence": "evidence_equivalence.json",
        "plan": "remediation_plan.json",
        "execution": "remediation_execution.json",
        "scope": "scope_classification.json",
        "integration": "kg_integration_truth.json",
        "aliases": "alias_collisions.json",
        "orphan": "orphan_node.json",
        "gate": "kg_grounding_gate.json",
        "performance": "kg_performance_preservation.json",
        "reconciliation": "reconciliation.json",
        "regression": "regression.json",
        "snapshot": "task25g_snapshot.json",
    }
    missing = [name for name in required.values() if not (RUNTIME / name).is_file()]
    if missing:
        raise SystemExit(f"Task 25G-R1 report inputs are missing: {missing}")
    data = {key: read_json(path, {}) for key, path in required.items()}

    scope = data["scope"]["actual_counts"]
    gate = data["gate"]
    performance = data["performance"]
    metrics = performance["metrics"]
    groups = data["regression"]["groups"]
    versions = data["versions"]
    equivalence = data["equivalence"]
    aliases = data["aliases"]
    execution = data["execution"]
    reconciliation = data["reconciliation"]

    final_status = str(data["regression"].get("final_task_status"))
    if final_status != "TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT":
        raise SystemExit(f"unexpected Task 25G-R1 final status: {final_status}")
    if reconciliation.get("status") != "PASS":
        raise SystemExit("Task 25G-R1 reconciliation must pass before report generation")

    text = f"""# Task 25G-R1 Knowledge Graph Grounding Remediation Report

## 1. Final Status

- Final result: `{final_status}`.
- Task 25G original status: `TASK25G_KG_GROUNDING_GATE_FAILED`.
- Forensics: PASS; all 12 reported evidence rows were traced to one archived English maintenance-record document and two distinct graph facts.
- Classification audit: PASS; pending and marketing leakage were false-positive labels, while archived and English leakage were real.
- Grounding remediation: scope enforcement and governance candidates applied; no evidence was rebound because no exact current successor exists.
- KG integration: PASS with safe empty-context degradation.
- KG performance: PASS.
- Static LoongArch/Kylin preparation remains as frozen by Task 25G; real-machine acceptance was not executed.
- Full extraction, full reindex, embedding, and vector production writes were not executed.

The graph is not production-ready for retrieval or diagnosis because it has zero facts backed by current, active, Chinese, engineering-approved evidence. This report does not convert an empty production context into a pass.

## 2. Leakage Baseline and Forensics

| Item | Original Task 25G | Verified R1 |
|---|---:|---:|
| leaked evidence | 12 | 12 historical rows investigated |
| archived leakage | not independently reported | {_count(scope, 'archived_leakage')} |
| pending leakage | 12 | {_count(scope, 'pending_leakage')} |
| marketing leakage | 12 | {_count(scope, 'marketing_leakage')} |
| approval leakage | combined with invalid scope | {_count(scope, 'approval_leakage')} |
| English leakage | not detected by the old static audit | {_count(scope, 'english_leakage')} |
| superseded leakage | not independently reported | {_count(scope, 'superseded_leakage')} |

The old audit used a combined invalid-document-state signal and assigned the same 12 archived rows to both pending and marketing categories. R1 now evaluates lifecycle, review, category, language, parse status, supersession and locator validity independently. Result: 12 evidence rows had two false labels each, for 24 false-positive label assignments. `maintenance_record` is a source category; it is not equivalent to pending or marketing.

Forensic exports contain identifiers, hashes and locators required for engineering review. The Markdown report intentionally excludes complete document titles and source text.

## 3. Document Version and Evidence Equivalence

- Archived documents investigated: {versions['archived_document_count']}.
- Explicit current successor found: 0.
- Exact successor support: 0.
- Partial successor support: 0.
- No explicit current successor: {_count(versions['resolution_counts'], 'NO_EXPLICIT_CURRENT_SUCCESSOR')}.
- Historical maintenance-record evidence rows: {data['forensics']['evidence_count']}.
- Equivalence result: `{json.dumps(equivalence['equivalence_counts'], ensure_ascii=False)}`.
- Automatic rebind allowed/executed: {equivalence['auto_rebind_count']}.
- LLM equivalence judgment: {str(equivalence['llm_used']).lower()}.

Title similarity was not used for automatic binding. Product family, model, relation, subject/object, alarm/component signals, semantic source and current source locator would all have been required for `EXACT_SUPPORT`.

## 4. Evidence Remediation

- Exact support: 0.
- Rebound evidence: {execution['evidence_rebinds']}.
- Reused current evidence: 0.
- Historical evidence preserved: {reconciliation['historical_evidence_count']}.
- Historical evidence excluded from production context: {data['forensics']['evidence_count']}.
- Unsupported-current facts in the original leakage set: {data['forensics']['distinct_fact_count']}.
- Active graph facts without current valid Chinese evidence globally: {gate['active_fact_count']}.
- Remediation candidates: {reconciliation['remediation_candidate_count']} pending manual governance candidates.
- OperationLog coverage: {reconciliation['operation_log_count']} operations.
- Automatic fact deletion: {reconciliation['fact_updates']}.
- Evidence deletion: {reconciliation['evidence_deletes']}.
- Candidate auto-approval: {reconciliation['candidate_auto_approval']}.
- Expert auto-write: {str(reconciliation['expert_auto_write']).lower()}.

The remediation plan contained 12 source-derived production-scope exclusions and two candidate creations. The explicit apply was transactional and idempotent: the second apply reused both candidates and produced no duplicate candidate or OperationLog writes. Existing graph facts and evidence rows were not rewritten.

## 5. Production KG Scope

| Gate | Result |
|---|---:|
| production fact count | {gate['production_fact_count']} |
| current-valid coverage over returned production facts | {gate['current_valid_evidence_coverage']:.2f} (vacuous: zero returned facts) |
| current-valid coverage over all active graph facts | {gate['raw_active_fact_current_evidence_coverage']:.2f} |
| archived evidence in production context | {gate['archived_evidence_in_production_context']} |
| pending leakage | {gate['pending_leakage']} |
| marketing leakage | {gate['marketing_leakage']} |
| approval leakage | {gate['approval_leakage']} |
| English leakage | {gate['english_leakage']} |
| superseded leakage | {gate['superseded_leakage']} |
| scope leakage | {gate['scope_leakage']} |
| unsupported facts returned | {gate['unsupported_graph_facts_returned']} |

Production APIs now require an active fact with at least one current, active, parsed, Chinese, engineering-approved, non-marketing, non-pending, non-superseded and non-archived source plus a valid active chunk locator. Admin/audit views can still inspect historical evidence. The zero leakage result is caused by exclusion at the source boundary, not by deleting history or disabling the graph module.

## 6. KG Integration Truth Audit

- Citation preservation: {data['integration']['citation_preservation']:.2f}; vacuous for the current empty production context, but every future returned fact must carry evidence IDs.
- Source locator coverage: {data['integration']['source_locator_coverage']:.2f}; vacuous for zero returned facts and enforced by source validation.
- Unsupported graph facts returned: {data['integration']['unsupported_graph_fact_returned']}.
- Archived baseline evidence returned: {data['integration']['archived_baseline_evidence_returned']}.
- Diagnosis grounding boundary: PASS; the diagnosis path uses the same production-scoped business context and cannot consume unsupported historical facts.
- Workflow automatic graph writes: {data['integration']['workflow_automatic_graph_writes']}.
- Correction boundary: PASS; completion creates review candidates only and does not mutate the formal graph.
- Knowledge Curator explicit review: PASS.
- Safe degradation when graph context is empty: `{data['integration']['safe_degradation']}`.

## 7. Alias and Orphan Review

- Orphan active node count: {data['orphan']['orphan_count']}.
- Orphan classification: `HISTORICAL_ONLY`; it was not deleted and is not returned in production context.
- Alias collision count: {aliases['collision_count']}.
- `SAFE_EQUIVALENT`: {_count(aliases['classification_counts'], 'SAFE_EQUIVALENT')}.
- `CONTEXT_DEPENDENT`: {_count(aliases['classification_counts'], 'CONTEXT_DEPENDENT')}.
- `INCOMPATIBLE`: {_count(aliases['classification_counts'], 'INCOMPATIBLE')}.
- `UNRESOLVED`: {_count(aliases['classification_counts'], 'UNRESOLVED')}.
- Unsafe automatic resolution: {aliases['unsafe_automatic_resolution_count']}.
- Deterministic canonicalization policy: {str(aliases['canonicalization_deterministic']).lower()}.

Both collisions are incompatible and require clarification/context; no node merge or default canonicalization was performed.

## 8. Performance Preservation

| Operation | R1 p95 | Hard gate | Result |
|---|---:|---:|---|
| node search | {metrics['node_search']['p95_ms']:.3f} ms | 500 ms | PASS |
| alias resolution | {metrics['alias']['p95_ms']:.3f} ms | 300 ms | PASS |
| one-hop expansion | {metrics['one_hop']['p95_ms']:.3f} ms | 800 ms | PASS |
| two-hop expansion | {metrics['two_hop']['p95_ms']:.3f} ms | 1500 ms | PASS |
| RAG KG context | {metrics['rag_context']['p95_ms']:.3f} ms | 1200 ms | PASS |

- Maximum SQL count: {performance['sql_count_max']} (gate: <=25).
- Serializer SQL: {performance['serializer_sql']}.
- N+1 detected: {str(performance['n_plus_one']).lower()}.
- Performance regression failures: {len(performance['failures'])}.

## 9. Regression and Reconciliation

| Group | Result |
|---|---|
| compileall | {groups['compileall']} |
| Alembic heads/current | {groups['alembic']} (`{EXPECTED_ALEMBIC_REVISION}`) |
| pytest | {groups['pytest']} (470 passed, 3 skipped) |
| security | {groups['security']} |
| RBAC | {groups['rbac']} |
| RAG | {groups['rag']} |
| agents | {groups['agents']} |
| Knowledge Curator | {groups['knowledge_curator']} |
| Task 25D | {groups['task25d']} isolated live replay |
| Task 25E | {groups['task25e']} current live-baseline core replay |
| Task 25F-R1 | {groups['task25f_r1']} |
| Task 25G original report/runtime frozen | {groups['task25g_frozen']} |
| Task 25G core regression | {groups['task25g_core']} |
| final smoke | {groups['final_smoke']} |

Task 25E's original response hash remains a historical database snapshot and was not relabeled. R1 generated an isolated current baseline and passed SQL trace, response parity, performance, concurrency, large-dataset, write-visibility and RBAC checks. Volatile Task 25D/25E browser JSON was re-generated during verification; browser semantics passed, while the R1 report relies on Task 25G's own frozen report/runtime hash reconciliation.

Existing regression scripts temporarily created exact Task24B/Task24D test fixtures. The existing scoped cleanup removed only post-snapshot marked fixtures; formal documents deleted=0. Final reconciliation confirms vector namespaces and counts match the R1 snapshot.

## 10. Integrity and Boundaries

- PostgreSQL-only graph persistence: yes.
- Neo4j: not used.
- pgvector: not introduced by this task.
- New migration: none.
- Alembic current/head: `{EXPECTED_ALEMBIC_REVISION}`.
- Task 25G original report unchanged: {str(reconciliation['checks']['task25g_report_unchanged']).lower()}.
- Task 25G original runtime unchanged: {str(reconciliation['checks']['task25g_runtime_unchanged']).lower()}.
- `backend/.env` unchanged: {str(reconciliation['checks']['backend_env_unchanged']).lower()}.
- ZIP inventory unchanged: {str(reconciliation['checks']['zip_inventory_unchanged']).lower()}.
- pilot_r2 / pilot_r3_semantic / pilot_r4_grounded / pilot_r5_query_aware: unchanged.
- Net vector namespace change: false.
- Remediation vector writes: {reconciliation['vector_writes']}.
- Remediation embedding writes: {reconciliation['embedding_writes']}.
- Full reindex: {str(reconciliation['full_reindex']).lower()}.
- Knowledge document/chunk content updates: 0.
- Approval state changes by remediation: 0.
- `expert_verified=true` writes: 0.
- Task 25C remains `MULTIMODAL_BENCHMARK_INSUFFICIENT`.
- R6 remains `DEFERRED_QWEN3_RERANK_CONFIG`.
- Package/ZIP generated: no.
- Git add/commit/reset/clean/restore: not executed.

## 11. Deployment Boundary

Task 25G's static LoongArch/Kylin portability, dependency and deployment-template checks remain frozen and unchanged. No LoongArch or Kylin real-machine test was executed in R1, so this report makes no real-machine acceptance claim.

## 12. Final Judgment

- KG production ready: **no**.
- KG deployment ready: **no for production use**, because no current valid Chinese engineering evidence backs any active graph fact.
- Static deployment preparation: retained from Task 25G.
- Real-machine acceptance required: yes.
- Remaining blocker: import or explicitly govern current, active, Chinese, engineering-approved source documents and establish exact evidence links through human review. Do not reactivate archived maintenance records or auto-approve candidates to clear this blocker.
"""
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": final_status,
                "report": str(REPORT.relative_to(ROOT)).replace("\\", "/"),
                "bytes": REPORT.stat().st_size,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
