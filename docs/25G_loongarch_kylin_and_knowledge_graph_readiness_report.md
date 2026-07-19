# Task 25G LoongArch/Kylin and Knowledge Graph Readiness Report

Generated at: 2026-07-15T08:40:58.145410+00:00

Final status: `TASK25G_KG_GROUNDING_GATE_FAILED`

This report is a Windows/x86 static and dry-run readiness audit. It does not claim real LoongArch or Kylin physical-machine acceptance. It does not package artifacts, does not submit Git changes, does not rebuild vectors, and does not approve knowledge graph candidates.

## 1. Current Baseline

- Alembic expected/current: `20260712_0015`
- Pytest regression observed: `PASS`
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
- RAG/diagnosis/workflow integration: PARTIAL
- Candidate approval boundary: explicit admin/expert approval required

## 3. KG Inventory

- nodes: 34
- active nodes: 34
- edges: 34
- active edges: 34
- aliases: 4
- evidence: 76
- extraction runs: 49
- candidates: 627

Node types:

- action: 3
- alarm: 2
- cause: 3
- component: 4
- device_model: 2
- fault: 4
- knowledge_chunk: 2
- knowledge_document: 2
- manufacturer: 2
- product_series: 3
- safety_risk: 2
- symptom: 2
- tool: 3

Relation types:

- BELONGS_TO: 5
- CAUSED_BY: 3
- CHECK_BY: 4
- DERIVED_FROM: 2
- HAS_ALARM: 2
- HAS_FAULT: 4
- HAS_SAFETY_RISK: 3
- HAS_SYMPTOM: 4
- RESOLVED_BY: 3
- USES_TOOL: 4

## 4. KG Integrity

- status: PASS
- issue count: 3
- critical/high issue count: 0
- duplicate active nodes: see `kg_integrity.json`
- duplicate active edges: see `kg_integrity.json`
- dangling edges: see `kg_integrity.json`
- orphan aliases: see `kg_integrity.json`
- invalid relations: 0 after allowing current production relation matrix
- invalid self-loops: 0

Issue preview:

```json
[
  {
    "problem_type": "orphan_active_node",
    "severity": "medium",
    "recommended_action": "Review and fix with explicit engineering approval.",
    "node_id": "7fea948b-ba57-4e5e-86a5-00894b859c7c",
    "node_type": "component",
    "source_ids": [
      "9f80195d-1915-4e6e-88ff-36181149e40f"
    ]
  },
  {
    "problem_type": "alias_collision",
    "severity": "medium",
    "recommended_action": "Classify as SAFE_EQUIVALENT, CONTEXT_DEPENDENT, INCOMPATIBLE, or UNRESOLVED before any merge.",
    "normalized_alias_hash": "66fd31a04d38644921fbc2d03f465cb5ca92e0da94045aabeb3e44faa69bb520",
    "node_count": 2,
    "classification": "UNRESOLVED"
  },
  {
    "problem_type": "alias_collision",
    "severity": "medium",
    "recommended_action": "Classify as SAFE_EQUIVALENT, CONTEXT_DEPENDENT, INCOMPATIBLE, or UNRESOLVED before any merge.",
    "normalized_alias_hash": "7ff1dc4d63c0cf3a49f85d6bf6f1eb332f336794262200f74b37aea0e91193c4",
    "node_count": 2,
    "classification": "UNRESOLVED"
  }
]
```

## 5. KG Grounding and Scope

- status: FAIL
- production evidence coverage: 1.0
- scope leakage count: 12
- pending leakage: 12
- marketing leakage: 12
- expert auto-write: False

Scope issue preview:

```json
[
  {
    "problem_type": "scope_leakage_document_state",
    "severity": "critical",
    "recommended_action": "Review and fix with explicit engineering approval.",
    "evidence_id": "794d7f7b-f55f-4c32-b0cf-a5477eef637b",
    "source_ids": [
      "approved",
      "archived",
      "parsed",
      "maintenance_record"
    ]
  },
  {
    "problem_type": "scope_leakage_document_state",
    "severity": "critical",
    "recommended_action": "Review and fix with explicit engineering approval.",
    "evidence_id": "d62d7934-da66-4a15-b93e-01e54c29674a",
    "source_ids": [
      "approved",
      "archived",
      "parsed",
      "maintenance_record"
    ]
  },
  {
    "problem_type": "scope_leakage_document_state",
    "severity": "critical",
    "recommended_action": "Review and fix with explicit engineering approval.",
    "evidence_id": "81941ff3-bebb-4055-8e2d-abdf67c75c05",
    "source_ids": [
      "approved",
      "archived",
      "parsed",
      "maintenance_record"
    ]
  },
  {
    "problem_type": "scope_leakage_document_state",
    "severity": "critical",
    "recommended_action": "Review and fix with explicit engineering approval.",
    "evidence_id": "f9c9916f-34e0-451a-85e3-df52d563c4bb",
    "source_ids": [
      "approved",
      "archived",
      "parsed",
      "maintenance_record"
    ]
  },
  {
    "problem_type": "scope_leakage_document_state",
    "severity": "critical",
    "recommended_action": "Review and fix with explicit engineering approval.",
    "evidence_id": "5ac4103e-f3ae-441e-8a0e-f05b0b749ba1",
    "source_ids": [
      "approved",
      "archived",
      "parsed",
      "maintenance_record"
    ]
  }
]
```

Current blocker: KG evidence references archived source documents. The audit reports this as `TASK25G_KG_GROUNDING_GATE_FAILED`. Task 25G did not delete or rewrite graph facts to hide this issue.

## 6. Alias / Identity

- alias count: 4
- alias collision issues: 2
- collision classes required before merge: SAFE_EQUIVALENT / CONTEXT_DEPENDENT / INCOMPATIBLE / UNRESOLVED
- automatic merge executed: no
- RAG canonicalization conflict audit: static only, see `kg_rag_integration.json`

## 7. Extraction Lineage

- status: PASS
- run count: 49
- candidate count: 627
- candidate status distribution: `{"approved": 14, "pending": 611, "rejected": 2}`
- automatic candidate approval in Task 25G: false

## 8. KG Integration

- RAG integration: PARTIAL
- Citation preservation: False
- diagnosis grounding: False
- workflow automatic graph writes: not_detected_by_static_audit
- correction candidate boundary: False
- safe degradation: available_if_business_context_returns_empty

## 9. KG Performance

- status: PASS
- sample count: 30
- serializer SQL: 0
- N+1: False
- traversal bounded: {"default_depth": 1, "max_depth": 2, "max_nodes": 200, "max_edges": 400, "query_timeout_ms": 1000}

Metrics:

```json
{
  "node_search": {
    "p50_ms": 1.45,
    "p95_ms": 87.708
  },
  "alias_resolution": {
    "p50_ms": 1.233,
    "p95_ms": 3.776
  },
  "one_hop": {
    "p50_ms": 1.313,
    "p95_ms": 4.498
  },
  "two_hop": {
    "p50_ms": 1.419,
    "p95_ms": 3.124
  },
  "evidence_expand": {
    "p50_ms": 1.494,
    "p95_ms": 7.931
  },
  "rag_context": {
    "p50_ms": 1.482,
    "p95_ms": 2.043
  }
}
```

## 10. KG Database and EXPLAIN

- PostgreSQL only: yes
- Neo4j required: no
- pgvector required for KG: no
- EXPLAIN status: PASS
- full plan text recorded: false
- migration added by Task 25G: no
- backup coverage: deployment scripts prepared; real target backup pending

## 11. Platform

- current platform: windows
- current architecture: amd64
- target OS: Kylin
- target architecture: loongarch64
- real LoongArch detected: false
- physical acceptance executed: false

## 12. Runtime Portability

- Windows runtime audit: PASS
- hardcoded drive path blockers: 0
- Windows-only subprocess/import blockers: 0
- frontend relative API audit: PASS
- browser visual check: UNAVAILABLE (Playwright package is installed but browser executable is missing on this Windows host; no browser download was performed by Task 25G.)

## 13. Dependencies

- production dependency audit: PASS
- production dependencies: 28
- native/system-library risk rows: 19
- unknown native dependencies: 0
- x86/Windows wheels in manifest: 0

Native dependency risk manifest status: PASS

## 14. Deployment

- release layout: prepared
- environment template: prepared
- systemd: PASS
- nginx: PASS
- backend install scripts: prepared
- frontend install scripts: prepared
- migration script: prepared
- KG verification in healthcheck: prepared
- backup: prepared
- rollback: PASS
- diagnostics: prepared

## 15. Resource Baseline

- workers: 2
- DB pool: 5 + overflow 1 per worker
- KG traversal limits: `{"default_depth": 1, "max_depth": 2, "max_nodes": 200, "max_edges": 400, "query_timeout_ms": 1000}`
- current RSS: 4.27
- frontend size: 718723
- 4-core/8GB static readiness: prepared, real machine measurement pending

## 16. Regression

Regression groups:

- compileall: PASS
- alembic: PASS
- pytest: PASS
- security: PASS
- rbac: PASS
- rag: PASS
- agents: PASS
- conversion: PASS
- frontend: PASS
- task25d: PASS
- task25e: PASS
- task25f_r1: PASS
- final_smoke: PASS

- browser: UNAVAILABLE
- final smoke: PASS

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
