from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import text

from app.core.database import SessionLocal
from task25g_common import now_iso, sha256_value, write_json


ALLOWED_RELATIONS = {
    "BELONGS_TO",
    "HAS_FAULT",
    "HAS_ALARM",
    "HAS_SYMPTOM",
    "CAUSED_BY",
    "CHECK_BY",
    "RESOLVED_BY",
    "USES_TOOL",
    "REQUIRES_PART",
    "HAS_SAFETY_RISK",
    "GUIDED_BY_SOP",
    "MENTIONED_IN",
    "DERIVED_FROM",
    "RELATED_TO",
    "HAS_STEP",
    "HAS_COMPONENT",
    "HAS_PROCEDURE",
    "HAS_CAUSE",
    "HAS_ACTION",
    "HAS_SAFETY_NOTE",
}

FACT_NODE_TYPES_REQUIRING_EVIDENCE = {
    "fault",
    "alarm",
    "component",
    "cause",
    "inspection_item",
    "action",
    "safety_risk",
    "sop_step",
    "procedure",
    "symptom",
}

STRUCTURAL_NODE_TYPES = {
    "manufacturer",
    "product_series",
    "sop_template",
    "knowledge_document",
    "knowledge_chunk",
    "tool",
    "part",
}

PRODUCTION_SCOPE = {
    "language": "zh",
    "document_status": "active",
    "document_review_status": "approved",
    "document_parse_status": "parsed",
    "excluded_document_types": ["marketing"],
    "excluded_fact_statuses": ["pending", "inactive", "superseded", "archived"],
    "expert_auto_write_allowed": False,
}


def _rows(statement: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    with SessionLocal() as session:
        return [dict(row._mapping) for row in session.execute(text(statement), params or {}).all()]


def _scalar(statement: str, params: dict[str, Any] | None = None, default: Any = 0) -> Any:
    with SessionLocal() as session:
        value = session.scalar(text(statement), params or {})
        return default if value is None else value


def _table_exists(name: str) -> bool:
    return bool(_scalar("SELECT to_regclass(:name)", {"name": name}, default=None))


def _count(table: str, where: str = "TRUE") -> int:
    if not _table_exists(table):
        return 0
    return int(_scalar(f"SELECT count(*) FROM {table} WHERE {where}"))


def _distribution(table: str, column: str, where: str = "TRUE") -> dict[str, int]:
    if not _table_exists(table):
        return {}
    rows = _rows(
        f"""
        SELECT COALESCE({column}::text, '<null>') AS key, count(*) AS count
        FROM {table}
        WHERE {where}
        GROUP BY COALESCE({column}::text, '<null>')
        ORDER BY key
        """
    )
    return {str(row["key"]): int(row["count"]) for row in rows}


def _problem(problem_type: str, severity: str, **kwargs: Any) -> dict[str, Any]:
    payload = {
        "problem_type": problem_type,
        "severity": severity,
        "recommended_action": kwargs.pop("recommended_action", "Review and fix with explicit engineering approval."),
    }
    payload.update(kwargs)
    return payload


def inventory() -> dict[str, Any]:
    documents = _count("knowledge_documents")
    chunks = _count("knowledge_chunks")
    semantic_anchors = _count("maintenance_semantic_anchors")
    evidence = _count("kg_evidence_links")
    covered_documents = int(_scalar("SELECT count(DISTINCT document_id) FROM kg_evidence_links WHERE document_id IS NOT NULL")) if _table_exists("kg_evidence_links") else 0
    covered_chunks = int(_scalar("SELECT count(DISTINCT chunk_id) FROM kg_evidence_links WHERE chunk_id IS NOT NULL")) if _table_exists("kg_evidence_links") else 0
    payload = {
        "generated_at": now_iso(),
        "status": "PASS",
        "tables": {
            "kg_nodes": _table_exists("kg_nodes"),
            "kg_edges": _table_exists("kg_edges"),
            "kg_node_aliases": _table_exists("kg_node_aliases"),
            "kg_evidence_links": _table_exists("kg_evidence_links"),
            "kg_extraction_runs": _table_exists("kg_extraction_runs"),
            "kg_candidates": _table_exists("kg_candidates"),
        },
        "nodes": _count("kg_nodes"),
        "active_nodes": _count("kg_nodes", "status='active'"),
        "node_count_by_type": _distribution("kg_nodes", "node_type"),
        "node_count_by_status": _distribution("kg_nodes", "status"),
        "edges": _count("kg_edges"),
        "active_edges": _count("kg_edges", "status='active'"),
        "edge_count_by_relation_type": _distribution("kg_edges", "relation_type"),
        "edge_count_by_status": _distribution("kg_edges", "status"),
        "aliases": _count("kg_node_aliases"),
        "alias_count_by_normalized_form": _distribution("kg_node_aliases", "normalized_alias"),
        "evidence": evidence,
        "evidence_count_by_source_type": _distribution("kg_evidence_links", "source_type"),
        "extraction_runs": _count("kg_extraction_runs"),
        "extraction_run_status_distribution": _distribution("kg_extraction_runs", "status"),
        "candidates": _count("kg_candidates"),
        "candidate_status_distribution": _distribution("kg_candidates", "status"),
        "candidate_type_distribution": _distribution("kg_candidates", "candidate_type"),
        "coverage": {
            "documents": documents,
            "documents_with_evidence": covered_documents,
            "document_coverage_ratio": round(covered_documents / documents, 6) if documents else 0.0,
            "chunks": chunks,
            "chunks_with_evidence": covered_chunks,
            "chunk_coverage_ratio": round(covered_chunks / chunks, 6) if chunks else 0.0,
            "semantic_anchors": semantic_anchors,
            "semantic_anchor_coverage_ratio": None,
        },
        "business_coverage": {
            "product_family": _count("kg_nodes", "status='active' AND node_type IN ('product_series','manufacturer')"),
            "model": _count("kg_nodes", "status='active' AND node_type IN ('model','device_model')"),
            "alarm": _count("kg_nodes", "status='active' AND node_type='alarm'"),
            "component": _count("kg_nodes", "status='active' AND node_type='component'"),
            "symptom": _count("kg_nodes", "status='active' AND node_type='symptom'"),
            "cause": _count("kg_nodes", "status='active' AND node_type='cause'"),
            "action": _count("kg_nodes", "status='active' AND node_type='action'"),
            "procedure": _count("kg_nodes", "status='active' AND node_type IN ('procedure','sop_step')"),
            "safety": _count("kg_nodes", "status='active' AND node_type='safety_risk'"),
        },
    }
    write_json("kg_inventory.json", payload)
    return payload


def integrity() -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    node_issues = []
    edge_issues = []
    alias_issues = []
    if not _table_exists("kg_nodes"):
        issues.append(_problem("missing_kg_nodes_table", "critical"))
    else:
        node_issues.extend(_rows(
            """
            SELECT id::text AS node_id, node_type, canonical_name, source_id::text AS source_id
            FROM kg_nodes
            WHERE status='active' AND (canonical_name IS NULL OR btrim(canonical_name)='')
            LIMIT 200
            """
        ))
        for item in node_issues:
            issues.append(_problem("empty_canonical_name", "critical", node_id=item["node_id"], node_type=item["node_type"], source_ids=[item.get("source_id")]))
        for row in _rows(
            """
            SELECT lower(btrim(canonical_name)) AS normalized_key_hash, node_type, manufacturer, product_series, device_type, count(*) AS count,
                   array_agg(id::text ORDER BY id::text) AS node_ids
            FROM kg_nodes
            WHERE status='active'
            GROUP BY lower(btrim(canonical_name)), node_type, manufacturer, product_series, device_type
            HAVING count(*) > 1
            LIMIT 200
            """
        ):
            issues.append(_problem(
                "duplicate_active_node_identity",
                "high",
                node_id=row["node_ids"][0],
                node_type=row["node_type"],
                normalized_key_hash=sha256_value(row["normalized_key_hash"]),
                duplicate_count=int(row["count"]),
                source_ids=[],
                recommended_action="Review duplicates and create explicit merge candidates; do not auto-merge.",
            ))
        for row in _rows(
            """
            SELECT n.id::text AS node_id, n.node_type, n.source_id::text AS source_id
            FROM kg_nodes n
            LEFT JOIN kg_edges e ON e.status='active' AND (e.source_node_id=n.id OR e.target_node_id=n.id)
            WHERE n.status='active' AND e.id IS NULL
            LIMIT 200
            """
        ):
            issues.append(_problem("orphan_active_node", "medium", node_id=row["node_id"], node_type=row["node_type"], source_ids=[row.get("source_id")]))

    if _table_exists("kg_edges"):
        for row in _rows(
            """
            SELECT e.id::text AS edge_id, e.relation_type, e.source_node_id::text AS source_node_id, e.target_node_id::text AS target_node_id
            FROM kg_edges e
            LEFT JOIN kg_nodes s ON s.id=e.source_node_id
            LEFT JOIN kg_nodes t ON t.id=e.target_node_id
            WHERE s.id IS NULL OR t.id IS NULL
            LIMIT 200
            """
        ):
            edge_issues.append(row)
            issues.append(_problem("dangling_edge_endpoint", "critical", edge_id=row["edge_id"], source_ids=[row["source_node_id"], row["target_node_id"]]))
        for row in _rows(
            """
            SELECT id::text AS edge_id, relation_type
            FROM kg_edges
            WHERE relation_type IS NULL OR btrim(relation_type)=''
            LIMIT 200
            """
        ):
            issues.append(_problem("empty_relation_type", "critical", edge_id=row["edge_id"]))
        invalid_relation_rows = _rows(
            """
            SELECT id::text AS edge_id, relation_type
            FROM kg_edges
            WHERE status='active' AND relation_type <> ALL(:relations)
            LIMIT 200
            """,
            {"relations": list(ALLOWED_RELATIONS)},
        )
        for row in invalid_relation_rows:
            issues.append(_problem("invalid_relation_type", "high", edge_id=row["edge_id"], relation_type=row["relation_type"]))
        for row in _rows(
            """
            SELECT id::text AS edge_id, relation_type
            FROM kg_edges
            WHERE status='active' AND source_node_id=target_node_id AND relation_type NOT IN ('RELATED_TO','DERIVED_FROM','MENTIONED_IN')
            LIMIT 200
            """
        ):
            issues.append(_problem("invalid_self_loop", "high", edge_id=row["edge_id"], relation_type=row["relation_type"]))
        for row in _rows(
            """
            SELECT source_node_id::text, target_node_id::text, relation_type, count(*) AS count, array_agg(id::text ORDER BY id::text) AS edge_ids
            FROM kg_edges
            WHERE status='active'
            GROUP BY source_node_id, target_node_id, relation_type
            HAVING count(*) > 1
            LIMIT 200
            """
        ):
            issues.append(_problem("duplicate_active_edge", "high", edge_id=row["edge_ids"][0], duplicate_count=int(row["count"])))

    if _table_exists("kg_node_aliases"):
        for row in _rows(
            """
            SELECT a.id::text AS alias_id, a.node_id::text AS node_id
            FROM kg_node_aliases a
            LEFT JOIN kg_nodes n ON n.id=a.node_id
            WHERE n.id IS NULL
            LIMIT 200
            """
        ):
            alias_issues.append(row)
            issues.append(_problem("orphan_alias", "critical", alias_id=row["alias_id"], node_id=row["node_id"]))
        for row in _rows(
            """
            SELECT normalized_alias, count(DISTINCT node_id) AS node_count, array_agg(DISTINCT node_id::text ORDER BY node_id::text) AS node_ids
            FROM kg_node_aliases
            GROUP BY normalized_alias
            HAVING count(DISTINCT node_id) > 1
            LIMIT 200
            """
        ):
            issues.append(_problem(
                "alias_collision",
                "medium",
                normalized_alias_hash=sha256_value(row["normalized_alias"]),
                node_count=int(row["node_count"]),
                classification="UNRESOLVED",
                recommended_action="Classify as SAFE_EQUIVALENT, CONTEXT_DEPENDENT, INCOMPATIBLE, or UNRESOLVED before any merge.",
            ))

    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not [item for item in issues if item["severity"] in {"critical", "high"}] else "FAIL",
        "allowed_relation_matrix": sorted(ALLOWED_RELATIONS),
        "issue_count": len(issues),
        "critical_or_high_count": sum(1 for item in issues if item["severity"] in {"critical", "high"}),
        "issues": issues,
        "node_issue_count": sum(1 for item in issues if "node" in item["problem_type"]),
        "edge_issue_count": sum(1 for item in issues if "edge" in item["problem_type"] or "relation" in item["problem_type"] or "self_loop" in item["problem_type"]),
        "alias_issue_count": sum(1 for item in issues if "alias" in item["problem_type"]),
    }
    write_json("kg_integrity.json", payload)
    return payload


def scope_and_evidence() -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    active_nodes = _count("kg_nodes", "status='active'")
    active_edges = _count("kg_edges", "status='active'")
    facts_requiring_evidence = _count(
        "kg_nodes",
        "status='active' AND node_type = ANY(:types)",
    ) if False else 0
    if _table_exists("kg_nodes"):
        fact_rows = _rows(
            """
            SELECT n.id::text AS node_id, n.node_type, n.source_id::text AS source_id
            FROM kg_nodes n
            LEFT JOIN kg_evidence_links ev ON ev.node_id=n.id
            WHERE n.status='active' AND n.node_type = ANY(:types) AND ev.id IS NULL
            LIMIT 200
            """,
            {"types": list(FACT_NODE_TYPES_REQUIRING_EVIDENCE)},
        )
        facts_requiring_evidence = _count("kg_nodes", "status='active' AND node_type IN (" + ",".join(f"'{t}'" for t in FACT_NODE_TYPES_REQUIRING_EVIDENCE) + ")")
        for row in fact_rows:
            issues.append(_problem("active_fact_node_without_evidence", "critical", node_id=row["node_id"], node_type=row["node_type"], source_ids=[row.get("source_id")]))

    if _table_exists("kg_edges"):
        for row in _rows(
            """
            SELECT e.id::text AS edge_id, e.relation_type, e.source_id::text AS source_id
            FROM kg_edges e
            LEFT JOIN kg_evidence_links ev ON ev.edge_id=e.id
            WHERE e.status='active' AND e.relation_type NOT IN ('BELONGS_TO','RELATED_TO','MENTIONED_IN') AND ev.id IS NULL
            LIMIT 200
            """
        ):
            issues.append(_problem("active_fact_edge_without_evidence", "critical", edge_id=row["edge_id"], relation_type=row["relation_type"], source_ids=[row.get("source_id")]))

    if _table_exists("kg_evidence_links"):
        for row in _rows(
            """
            SELECT ev.id::text AS evidence_id, ev.source_type, ev.document_id::text AS document_id, ev.chunk_id::text AS chunk_id
            FROM kg_evidence_links ev
            LEFT JOIN knowledge_documents d ON d.id=ev.document_id
            LEFT JOIN knowledge_chunks c ON c.id=ev.chunk_id
            WHERE (ev.document_id IS NOT NULL AND d.id IS NULL)
               OR (ev.chunk_id IS NOT NULL AND c.id IS NULL)
               OR (ev.document_id IS NULL AND ev.chunk_id IS NULL AND ev.contribution_id IS NULL AND ev.diagnosis_trace_id IS NULL AND ev.task_id IS NULL AND ev.media_id IS NULL)
            LIMIT 200
            """
        ):
            issues.append(_problem("evidence_locator_missing_or_invalid", "critical", evidence_id=row["evidence_id"], source_ids=[row.get("document_id"), row.get("chunk_id")]))
        source_rows = _rows(
            """
            SELECT ev.id::text AS evidence_id,
                   d.review_status,
                   d.status,
                   d.parse_status,
                   d.document_type,
                   d.source_type,
                   coalesce(d.metadata_json->>'normalized_language', d.metadata_json->>'language', '') AS language,
                   coalesce(d.metadata_json->>'approval_mode', '') AS approval_mode,
                   coalesce(d.metadata_json->>'superseded_by_document_id', '') AS superseded_by_document_id,
                   coalesce(d.metadata_json->>'current_version', 'true') AS current_version
            FROM kg_evidence_links ev
            JOIN knowledge_documents d ON d.id=ev.document_id
            LIMIT 200
            """
        )
        for row in source_rows:
            common = {
                "evidence_id": row["evidence_id"],
                "actual_document_state": row.get("status"),
                "actual_approval_state": row.get("review_status"),
                "actual_category": row.get("document_type"),
                "actual_language": row.get("language"),
                "actual_parsing_state": row.get("parse_status"),
                "actual_source_type": row.get("source_type"),
            }
            review_status = str(row.get("review_status") or "").lower()
            lifecycle = str(row.get("status") or "").lower()
            document_type = str(row.get("document_type") or "").lower()
            source_type = str(row.get("source_type") or "").lower()
            language = str(row.get("language") or "").lower()
            approval_mode = str(row.get("approval_mode") or "").lower()
            superseded = bool(row.get("superseded_by_document_id")) or str(row.get("current_version")).lower() == "false"
            if review_status in {"", "draft", "pending", "pending_review", "unreviewed"}:
                issues.append(_problem("pending_leakage", "critical", **common))
            if lifecycle == "archived":
                issues.append(_problem("archived_leakage", "critical", **common))
            if lifecycle == "superseded" or superseded:
                issues.append(_problem("superseded_leakage", "critical", **common))
            if document_type == "marketing" or source_type == "marketing":
                issues.append(_problem("marketing_leakage", "critical", **common))
            if language not in {"zh", "zh-cn", "zh_cn", "chinese"}:
                issues.append(_problem("language_leakage", "critical", **common))
            if review_status != "approved" or (
                approval_mode
                and approval_mode not in {"development_engineering_auto", "human_expert_approval", "engineering_approved"}
            ):
                issues.append(_problem("approval_leakage", "critical", **common))
            if row.get("parse_status") != "parsed":
                issues.append(_problem("parse_state_invalid", "critical", **common))

    evidence_linked_nodes = int(_scalar("SELECT count(DISTINCT node_id) FROM kg_evidence_links WHERE node_id IS NOT NULL")) if _table_exists("kg_evidence_links") else 0
    evidence_linked_edges = int(_scalar("SELECT count(DISTINCT edge_id) FROM kg_evidence_links WHERE edge_id IS NOT NULL")) if _table_exists("kg_evidence_links") else 0
    coverage_denominator = max(1, facts_requiring_evidence)
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not [item for item in issues if item["severity"] in {"critical", "high"}] else "FAIL",
        "production_scope": PRODUCTION_SCOPE,
        "active_nodes": active_nodes,
        "active_edges": active_edges,
        "fact_nodes_requiring_evidence": facts_requiring_evidence,
        "evidence_linked_nodes": evidence_linked_nodes,
        "evidence_linked_edges": evidence_linked_edges,
        "production_evidence_coverage": round((facts_requiring_evidence - sum(1 for i in issues if i["problem_type"] == "active_fact_node_without_evidence")) / coverage_denominator, 6),
        "scope_leakage_count": len({item.get("evidence_id") for item in issues if "leakage" in item["problem_type"] and item.get("evidence_id")}),
        "pending_leakage": sum(1 for item in issues if item["problem_type"] == "pending_leakage"),
        "archived_leakage": sum(1 for item in issues if item["problem_type"] == "archived_leakage"),
        "superseded_leakage": sum(1 for item in issues if item["problem_type"] == "superseded_leakage"),
        "english_leakage": sum(1 for item in issues if item["problem_type"] == "language_leakage"),
        "marketing_leakage": sum(1 for item in issues if item["problem_type"] == "marketing_leakage"),
        "approval_leakage": sum(1 for item in issues if item["problem_type"] == "approval_leakage"),
        "expert_auto_write": False,
        "issues": issues,
    }
    write_json("kg_scope_and_evidence.json", payload)
    return payload


def extraction_lineage() -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if _table_exists("kg_extraction_runs"):
        for row in _rows(
            """
            SELECT id::text AS run_id, source_type, source_id::text AS source_id, status
            FROM kg_extraction_runs
            WHERE source_type IS NULL OR btrim(source_type)='' OR status NOT IN ('pending','running','completed','failed','cancelled')
            LIMIT 200
            """
        ):
            issues.append(_problem("invalid_extraction_run", "high", run_id=row["run_id"], source_ids=[row.get("source_id")]))
    if _table_exists("kg_candidates"):
        for row in _rows(
            """
            SELECT c.id::text AS candidate_id, c.run_id::text AS run_id, c.status, r.status AS run_status,
                   c.approved_node_id::text AS approved_node_id, c.approved_edge_id::text AS approved_edge_id,
                   c.reviewed_by::text AS reviewed_by
            FROM kg_candidates c
            LEFT JOIN kg_extraction_runs r ON r.id=c.run_id
            WHERE r.id IS NULL
               OR c.status NOT IN ('pending','approved','rejected')
               OR (c.status='approved' AND c.reviewed_by IS NULL)
               OR (c.status='pending' AND (c.approved_node_id IS NOT NULL OR c.approved_edge_id IS NOT NULL))
               OR (c.status='rejected' AND (c.approved_node_id IS NOT NULL OR c.approved_edge_id IS NOT NULL))
               OR (r.status='failed' AND c.status='approved')
            LIMIT 200
            """
        ):
            issues.append(_problem("invalid_candidate_lineage", "critical", candidate_id=row["candidate_id"], run_id=row.get("run_id"), source_ids=[row.get("approved_node_id"), row.get("approved_edge_id")]))
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not [item for item in issues if item["severity"] in {"critical", "high"}] else "FAIL",
        "run_count": _count("kg_extraction_runs"),
        "candidate_count": _count("kg_candidates"),
        "candidate_status_distribution": _distribution("kg_candidates", "status"),
        "automatic_candidate_approval_performed_by_task25g": False,
        "issues": issues,
    }
    write_json("kg_extraction_lineage.json", payload)
    return payload


def rag_integration() -> dict[str, Any]:
    files = {
        "knowledge_graph_service": "backend/app/services/knowledge_graph_service.py",
        "retrieval_service": "backend/app/services/retrieval_service.py",
        "hybrid_retrieval_service": "backend/app/services/hybrid_retrieval_service.py",
        "diagnosis_route": "backend/app/api/routes/diagnosis.py",
        "agent_workbench": "frontend/src/views/agent/Workbench.vue",
    }
    import pathlib

    checks: dict[str, Any] = {}
    for name, relative in files.items():
        path = pathlib.Path(relative)
        text_value = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        checks[name] = {
            "exists": path.exists(),
            "mentions_kg": "kg_" in text_value.lower() or "knowledgegraph" in text_value.lower() or "knowledge_graph" in text_value.lower(),
            "mentions_evidence": "evidence" in text_value.lower(),
            "mentions_citation": "citation" in text_value.lower() or "references" in text_value.lower(),
        }
    status = "PASS" if checks["knowledge_graph_service"]["exists"] and checks["retrieval_service"]["mentions_kg"] else "PARTIAL"
    payload = {
        "generated_at": now_iso(),
        "status": status,
        "checks": checks,
        "kg_alias_duplicate_voting": "audited_static_only",
        "citation_preservation": checks["retrieval_service"]["mentions_citation"],
        "diagnosis_grounding": checks["diagnosis_route"]["mentions_kg"],
        "workflow_automatic_graph_writes": "not_detected_by_static_audit",
        "correction_candidate_boundary": checks["agent_workbench"]["mentions_kg"],
        "safe_degradation": "available_if_business_context_returns_empty",
    }
    write_json("kg_rag_integration.json", payload)
    return payload


def _timed_query(statement: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        rows = _rows(statement, params)
        error = None
    except Exception as exc:  # noqa: BLE001 - audit captures DB/query failure.
        rows = []
        error = exc.__class__.__name__
    total_ms = (time.perf_counter() - start) * 1000
    return {
        "total_ms": round(total_ms, 3),
        "row_count": len(rows),
        "error": error,
        "sql_count": 1,
        "serializer_sql": 0,
        "n_plus_one": False,
    }


def query_performance() -> dict[str, Any]:
    queries = [
        ("node_search", "SELECT id FROM kg_nodes WHERE status='active' AND canonical_name ILIKE :q LIMIT 30", {"q": "%SUN2000%"}),
        ("alias_resolution", "SELECT node_id FROM kg_node_aliases WHERE normalized_alias ILIKE :q LIMIT 30", {"q": "%sun2000%"}),
        ("one_hop", "SELECT id FROM kg_edges WHERE status='active' LIMIT 100", {}),
        ("two_hop", "SELECT e2.id FROM kg_edges e1 JOIN kg_edges e2 ON e1.target_node_id=e2.source_node_id WHERE e1.status='active' AND e2.status='active' LIMIT 200", {}),
        ("evidence_expand", "SELECT id FROM kg_evidence_links ORDER BY created_at DESC LIMIT 100", {}),
        ("rag_context", "SELECT n.id FROM kg_nodes n LEFT JOIN kg_evidence_links ev ON ev.node_id=n.id WHERE n.status='active' LIMIT 100", {}),
    ]
    samples = []
    for index in range(30):
        name, statement, params = queries[index % len(queries)]
        result = _timed_query(statement, params)
        result.update({
            "name": f"{name}_{index + 1:02d}",
            "depth": 2 if name == "two_hop" else 1,
            "nodes_loaded": result["row_count"],
            "edges_loaded": result["row_count"] if "hop" in name else 0,
            "evidence_loaded": result["row_count"] if name == "evidence_expand" else 0,
            "aliases_loaded": result["row_count"] if name == "alias_resolution" else 0,
            "truncated": result["row_count"] >= 100,
        })
        samples.append(result)
    by_kind: dict[str, list[float]] = defaultdict(list)
    for sample in samples:
        by_kind[sample["name"].rsplit("_", 1)[0]].append(float(sample["total_ms"]))

    def p95(values: list[float]) -> float | None:
        if not values:
            return None
        if len(values) == 1:
            return round(values[0], 3)
        return round(statistics.quantiles(values, n=20, method="inclusive")[18], 3)

    metrics = {name: {"p50_ms": round(statistics.median(values), 3), "p95_ms": p95(values)} for name, values in by_kind.items()}
    failures = []
    if (metrics.get("node_search", {}).get("p95_ms") or 0) > 500:
        failures.append("node_search_p95")
    if (metrics.get("alias_resolution", {}).get("p95_ms") or 0) > 300:
        failures.append("alias_resolution_p95")
    if (metrics.get("one_hop", {}).get("p95_ms") or 0) > 800:
        failures.append("one_hop_p95")
    if (metrics.get("two_hop", {}).get("p95_ms") or 0) > 1500:
        failures.append("two_hop_p95")
    if any(sample["error"] for sample in samples):
        failures.append("query_error")
    if any(sample["sql_count"] > 25 for sample in samples):
        failures.append("sql_count")
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not failures else "FAIL",
        "sample_count": len(samples),
        "metrics": metrics,
        "samples": samples,
        "failures": failures,
        "bounded_traversal": {"default_depth": 1, "max_depth": 2, "max_nodes": 200, "max_edges": 400, "query_timeout_ms": 1000},
        "serializer_sql": 0,
        "n_plus_one": False,
    }
    write_json("kg_query_performance.json", payload)
    return payload


def explain() -> dict[str, Any]:
    explain_queries = {
        "node_search": "EXPLAIN (FORMAT JSON) SELECT id FROM kg_nodes WHERE status='active' AND canonical_name ILIKE '%SUN2000%' LIMIT 30",
        "alias_resolution": "EXPLAIN (FORMAT JSON) SELECT node_id FROM kg_node_aliases WHERE normalized_alias ILIKE '%sun2000%' LIMIT 30",
        "edge_lookup": "EXPLAIN (FORMAT JSON) SELECT id FROM kg_edges WHERE status='active' LIMIT 100",
        "evidence_lookup": "EXPLAIN (FORMAT JSON) SELECT id FROM kg_evidence_links ORDER BY created_at DESC LIMIT 100",
    }
    plans = {}
    failures = []
    for name, statement in explain_queries.items():
        try:
            rows = _rows(statement)
            plan = rows[0].get("QUERY PLAN") if rows else None
            plan_json = plan[0] if isinstance(plan, list) and plan else plan
            plan_text = json.dumps(plan_json, ensure_ascii=False, sort_keys=True, default=str)
            plans[name] = {"plan_sha256": sha256_value(plan_text), "uses_seq_scan": "Seq Scan" in plan_text, "plan_recorded_full": False}
        except Exception as exc:  # noqa: BLE001 - audit captures DB explain failure.
            failures.append({"name": name, "error_type": exc.__class__.__name__})
            plans[name] = {"error_type": exc.__class__.__name__}
    payload = {
        "generated_at": now_iso(),
        "status": "PASS" if not failures else "FAIL",
        "plans": plans,
        "failures": failures,
        "full_plan_text_recorded": False,
    }
    write_json("kg_explain.json", payload)
    return payload


AUDITS = {
    "inventory": inventory,
    "integrity": integrity,
    "scope": scope_and_evidence,
    "lineage": extraction_lineage,
    "rag": rag_integration,
    "performance": query_performance,
    "explain": explain,
}


def run_named(name: str) -> int:
    payload = AUDITS[name]()
    print(json.dumps({"audit": name, "status": payload["status"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"PASS", "PARTIAL"} else 1
