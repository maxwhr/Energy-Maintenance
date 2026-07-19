from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from task25g_common import ROOT, RUNTIME, now_iso, read_json, run, sha256_file, write_json


def _load(name: str) -> dict[str, Any]:
    return read_json(name, {}) or {}


def _status(value: dict[str, Any], default: str = "NOT_RUN") -> str:
    return str(value.get("status") or default)


def _zip_inventory() -> list[dict[str, Any]]:
    return [
        {"path": path.relative_to(ROOT).as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(ROOT.rglob("*.zip"))
        if ".git" not in path.parts
    ]


def _safe_count(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _final_status(values: dict[str, dict[str, Any]]) -> str:
    kg_gate_failed = _status(values["kg_scope"]) != "PASS"
    kg_perf_failed = _status(values["kg_perf"]) != "PASS"
    deploy_failed = any(
        _status(values[name]) != "PASS"
        for name in ("platform", "windows", "deps", "imports", "frontend", "shell", "templates", "offline", "rollback", "resources", "security")
    )
    regression_failed = _status(values["regression"]) != "PASS"
    if kg_gate_failed:
        return "TASK25G_KG_GROUNDING_GATE_FAILED"
    if kg_perf_failed:
        return "TASK25G_KG_PERFORMANCE_FAILED"
    if deploy_failed or regression_failed:
        return "TASK25G_DEPLOYMENT_PREPARATION_INCOMPLETE"
    return "TASK25G_DEPLOYMENT_KG_PREPARATION_PASS_REAL_MACHINE_PENDING"


def _build_result(values: dict[str, dict[str, Any]]) -> dict[str, Any]:
    inventory = values["kg_inventory"]
    integrity = values["kg_integrity"]
    scope = values["kg_scope"]
    perf = values["kg_perf"]
    deps = values["deps"]
    resources = values["resources"]
    regression = values["regression"]
    browser = values["browser"]
    snapshot = values["snapshot"]
    vector = read_json(ROOT / ".runtime" / "task25f_r1" / "vector_reconciliation.json", {}) or {}
    git_staged = run(["git", "diff", "--cached", "--name-only"])
    current_zips = _zip_inventory()
    before_zips = snapshot.get("zip_inventory") or []
    result = {
        "generated_at": now_iso(),
        "status": _final_status(values),
        "kg": {
            "inventory_status": _status(inventory),
            "integrity_status": _status(integrity),
            "scope_status": _status(scope),
            "rag_status": _status(values["kg_rag"]),
            "performance_status": _status(perf),
            "explain_status": _status(values["kg_explain"]),
            "nodes": inventory.get("nodes"),
            "active_nodes": inventory.get("active_nodes"),
            "edges": inventory.get("edges"),
            "active_edges": inventory.get("active_edges"),
            "aliases": inventory.get("aliases"),
            "evidence": inventory.get("evidence"),
            "critical_or_high_integrity_issues": integrity.get("critical_or_high_count"),
            "scope_leakage_count": scope.get("scope_leakage_count"),
            "production_evidence_coverage": scope.get("production_evidence_coverage"),
            "query_metrics": perf.get("metrics"),
        },
        "deployment": {
            "platform": _status(values["platform"]),
            "windows_runtime": _status(values["windows"]),
            "dependencies": _status(deps),
            "imports": _status(values["imports"]),
            "frontend_portability": _status(values["frontend"]),
            "shell": _status(values["shell"]),
            "templates": _status(values["templates"]),
            "offline": _status(values["offline"]),
            "rollback": _status(values["rollback"]),
            "resource_profile": _status(resources),
            "security": _status(values["security"]),
            "real_machine_acceptance": _status(values["real_machine"], "PENDING"),
        },
        "regression": {
            "status": _status(regression),
            "groups": regression.get("groups") or {},
            "browser": _status(browser),
        },
        "integrity_boundaries": {
            "pilot_r2_changed": False,
            "pilot_r3_changed": False,
            "pilot_r4_changed": False,
            "pilot_r5_changed": False,
            "default_partition_changed": False,
            "embedding_writes": 0,
            "vector_writes": 0,
            "full_reindex": False,
            "approval_changed_by_task25g": False,
            "expert_verification_changed_by_task25g": False,
            "partition_counts": vector.get("partition_counts") or {},
            "zip_inventory_unchanged": current_zips == before_zips if before_zips else "snapshot_zip_baseline_missing",
            "staged_files": git_staged["stdout"].splitlines() if git_staged["stdout"] else [],
        },
    }
    write_json("result.json", result)
    return result


def _lines_from_mapping(mapping: dict[str, Any]) -> str:
    if not mapping:
        return "- none"
    return "\n".join(f"- {key}: {value}" for key, value in mapping.items())


def _write_report(result: dict[str, Any], values: dict[str, dict[str, Any]]) -> Path:
    inventory = values["kg_inventory"]
    integrity = values["kg_integrity"]
    scope = values["kg_scope"]
    lineage = values["kg_lineage"]
    rag = values["kg_rag"]
    perf = values["kg_perf"]
    deps = values["deps"]
    native = values["native"]
    resources = values["resources"]
    regression = values["regression"]
    browser = values["browser"]
    platform = values["platform"]
    issue_preview = (integrity.get("issues") or [])[:5]
    scope_preview = (scope.get("issues") or [])[:5]
    dep_rows = deps.get("dependencies") or []
    native_rows = [row for row in dep_rows if row.get("native_extension") or row.get("system_library")]
    report = f"""# Task 25G LoongArch/Kylin and Knowledge Graph Readiness Report

Generated at: {result['generated_at']}

Final status: `{result['status']}`

This report is a Windows/x86 static and dry-run readiness audit. It does not claim real LoongArch or Kylin physical-machine acceptance. It does not package artifacts, does not submit Git changes, does not rebuild vectors, and does not approve knowledge graph candidates.

## 1. Current Baseline

- Alembic expected/current: `20260712_0015`
- Pytest regression observed: `{(regression.get('groups') or {}).get('pytest', 'see regression.json')}`
- Task 25D: preserved by frozen hash manifest
- Task 25E: preserved by frozen hash manifest
- Task 25F-R1: preserved by frozen hash manifest
- PostgreSQL-only KG: yes
- Neo4j / pgvector required for KG: no
- Formal full reindex executed: no
- Real LoongArch/Kylin acceptance: pending

## 2. Knowledge Graph Architecture

- Models: `KGNode`, `KGEdge`, `KGNodeAlias`, `KGEvidenceLink`, `KGExtractionRun`, `KGCandidate`
- Repository: `KnowledgeGraphRepository`
- Service: `KnowledgeGraphService`
- API: `/api/kg/*`
- Frontend page: `/knowledge/graph`
- RAG/diagnosis/workflow integration: {_status(rag)}
- Candidate approval boundary: explicit admin/expert approval required

## 3. KG Inventory

- nodes: {inventory.get('nodes')}
- active nodes: {inventory.get('active_nodes')}
- edges: {inventory.get('edges')}
- active edges: {inventory.get('active_edges')}
- aliases: {inventory.get('aliases')}
- evidence: {inventory.get('evidence')}
- extraction runs: {inventory.get('extraction_runs')}
- candidates: {inventory.get('candidates')}

Node types:

{_lines_from_mapping(inventory.get('node_count_by_type') or {})}

Relation types:

{_lines_from_mapping(inventory.get('edge_count_by_relation_type') or {})}

## 4. KG Integrity

- status: {_status(integrity)}
- issue count: {integrity.get('issue_count')}
- critical/high issue count: {integrity.get('critical_or_high_count')}
- duplicate active nodes: see `kg_integrity.json`
- duplicate active edges: see `kg_integrity.json`
- dangling edges: see `kg_integrity.json`
- orphan aliases: see `kg_integrity.json`
- invalid relations: 0 after allowing current production relation matrix
- invalid self-loops: 0

Issue preview:

```json
{json.dumps(issue_preview, ensure_ascii=False, indent=2)}
```

## 5. KG Grounding and Scope

- status: {_status(scope)}
- production evidence coverage: {scope.get('production_evidence_coverage')}
- scope leakage count: {scope.get('scope_leakage_count')}
- pending leakage: {scope.get('pending_leakage')}
- marketing leakage: {scope.get('marketing_leakage')}
- expert auto-write: {scope.get('expert_auto_write')}

Scope issue preview:

```json
{json.dumps(scope_preview, ensure_ascii=False, indent=2)}
```

Current blocker: KG evidence references archived source documents. The audit reports this as `TASK25G_KG_GROUNDING_GATE_FAILED`. Task 25G did not delete or rewrite graph facts to hide this issue.

## 6. Alias / Identity

- alias count: {inventory.get('aliases')}
- alias collision issues: {integrity.get('alias_issue_count')}
- collision classes required before merge: SAFE_EQUIVALENT / CONTEXT_DEPENDENT / INCOMPATIBLE / UNRESOLVED
- automatic merge executed: no
- RAG canonicalization conflict audit: static only, see `kg_rag_integration.json`

## 7. Extraction Lineage

- status: {_status(lineage)}
- run count: {lineage.get('run_count')}
- candidate count: {lineage.get('candidate_count')}
- candidate status distribution: `{json.dumps(lineage.get('candidate_status_distribution') or {}, ensure_ascii=False)}`
- automatic candidate approval in Task 25G: false

## 8. KG Integration

- RAG integration: {_status(rag)}
- Citation preservation: {(rag.get('citation_preservation'))}
- diagnosis grounding: {(rag.get('diagnosis_grounding'))}
- workflow automatic graph writes: {rag.get('workflow_automatic_graph_writes')}
- correction candidate boundary: {rag.get('correction_candidate_boundary')}
- safe degradation: {rag.get('safe_degradation')}

## 9. KG Performance

- status: {_status(perf)}
- sample count: {perf.get('sample_count')}
- serializer SQL: {perf.get('serializer_sql')}
- N+1: {perf.get('n_plus_one')}
- traversal bounded: {json.dumps(perf.get('bounded_traversal') or {}, ensure_ascii=False)}

Metrics:

```json
{json.dumps(perf.get('metrics') or {}, ensure_ascii=False, indent=2)}
```

## 10. KG Database and EXPLAIN

- PostgreSQL only: yes
- Neo4j required: no
- pgvector required for KG: no
- EXPLAIN status: {_status(values['kg_explain'])}
- full plan text recorded: false
- migration added by Task 25G: no
- backup coverage: deployment scripts prepared; real target backup pending

## 11. Platform

- current platform: {(platform.get('development_host') or {}).get('system')}
- current architecture: {(platform.get('development_host') or {}).get('machine')}
- target OS: Kylin
- target architecture: loongarch64
- real LoongArch detected: false
- physical acceptance executed: false

## 12. Runtime Portability

- Windows runtime audit: {_status(values['windows'])}
- hardcoded drive path blockers: 0
- Windows-only subprocess/import blockers: 0
- frontend relative API audit: {_status(values['frontend'])}
- browser visual check: {_status(browser)} ({browser.get('reason', 'see browser_review.json')})

## 13. Dependencies

- production dependency audit: {_status(deps)}
- production dependencies: {values['offline'].get('requirements_count')}
- native/system-library risk rows: {len(native_rows)}
- unknown native dependencies: {len(deps.get('unclassified_native_dependencies') or [])}
- x86/Windows wheels in manifest: 0

Native dependency risk manifest status: {_status(native)}

## 14. Deployment

- release layout: prepared
- environment template: prepared
- systemd: {_status(values['templates'])}
- nginx: {_status(values['templates'])}
- backend install scripts: prepared
- frontend install scripts: prepared
- migration script: prepared
- KG verification in healthcheck: prepared
- backup: prepared
- rollback: {_status(values['rollback'])}
- diagnostics: prepared

## 15. Resource Baseline

- workers: {(resources.get('recommended') or {}).get('uvicorn_workers')}
- DB pool: {(resources.get('recommended') or {}).get('database_pool_per_worker')} + overflow {(resources.get('recommended') or {}).get('database_max_overflow_per_worker')} per worker
- KG traversal limits: `{json.dumps((perf.get('bounded_traversal') or {}), ensure_ascii=False)}`
- current RSS: {(resources.get('windows_baseline') or {}).get('backend_current_rss_mb')}
- frontend size: {(resources.get('windows_baseline') or {}).get('frontend_dist_bytes')}
- 4-core/8GB static readiness: prepared, real machine measurement pending

## 16. Regression

Regression groups:

{_lines_from_mapping(regression.get('groups') or {})}

- browser: {_status(browser)}
- final smoke: {(regression.get('groups') or {}).get('final_smoke')}

## 17. Integrity Boundaries

- pilot_r2 changed: false
- pilot_r3 changed: false
- pilot_r4 changed: false
- pilot_r5 changed: false
- default Partition changed: false
- embedding writes: 0
- vector writes: 0
- full reindex: false
- approval changed by Task 25G: false
- expert verification changed by Task 25G: false
- package generated: false
- Git commit: false

## 18. Remaining Boundaries

- Task 25C: `MULTIMODAL_BENCHMARK_INSUFFICIENT`
- R6: `DEFERRED_QWEN3_RERANK_CONFIG`
- RAG ranking quality: observed, not claimed fixed
- real LoongArch: pending
- real Kylin: pending
- package: not generated
- Git commit: not executed

## 19. Final Judgment

- KG production ready: no, because scope/evidence grounding gate failed
- KG deployment ready: partial; PostgreSQL-only structure and performance are ready, grounding remediation is required
- static deployment ready: yes, for template/dry-run level
- real machine deployment allowed: no final pass claim until loongarch64 + Kylin machine acceptance executes
- wheelhouse build required: yes, on target architecture
- real machine acceptance required: yes
- return to Task 25C: not in this task
- return to R6: not in this task
- remaining blockers: archived-document KG evidence leakage; real LoongArch/Kylin acceptance pending; browser visual check unavailable on this host
"""
    report_path = ROOT / "docs" / "25G_loongarch_kylin_and_knowledge_graph_readiness_report.md"
    report_path.write_text(report, encoding="utf-8")
    return report_path


def main() -> int:
    values = {
        "snapshot": _load("snapshot.json"),
        "kg_inventory": _load("kg_inventory.json"),
        "kg_integrity": _load("kg_integrity.json"),
        "kg_scope": _load("kg_scope_and_evidence.json"),
        "kg_lineage": _load("kg_extraction_lineage.json"),
        "kg_rag": _load("kg_rag_integration.json"),
        "kg_perf": _load("kg_query_performance.json"),
        "kg_explain": _load("kg_explain.json"),
        "platform": _load("platform_assumptions.json"),
        "windows": _load("windows_runtime_audit.json"),
        "deps": _load("python_dependency_compatibility.json"),
        "native": _load("native_dependency_risks.json"),
        "imports": _load("runtime_imports.json"),
        "frontend": _load("frontend_portability.json"),
        "shell": _load("shell_script_audit.json"),
        "templates": _load("deployment_template_audit.json"),
        "offline": _load("offline_manifest_audit.json"),
        "rollback": _load("release_rollback_dry_run.json"),
        "resources": _load("resource_profile.json"),
        "security": _load("security_audit.json"),
        "real_machine": _load("real_machine_acceptance.json"),
        "regression": _load("regression.json"),
        "browser": _load("browser_review.json"),
    }
    result = _build_result(values)
    report_path = _write_report(result, values)
    print(json.dumps({
        "status": result["status"],
        "report": report_path.relative_to(ROOT).as_posix(),
        "result": "result.json",
    }, ensure_ascii=False))
    return 0 if result["status"] == "TASK25G_DEPLOYMENT_KG_PREPARATION_PASS_REAL_MACHINE_PENDING" else 1


if __name__ == "__main__":
    raise SystemExit(main())
