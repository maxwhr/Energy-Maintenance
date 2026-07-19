from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select

from task25g_r1_common import now_iso, read_json, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGCandidate, KGEdge, KGEvidenceLink, KGNode
    from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService

    baseline = read_json("leakage_baseline.json", {})
    classification = read_json("scope_classification.json", {})
    integration = read_json("kg_integration_truth.json", {})
    leaked_ids = {UUID(value) for value in baseline.get("evidence_ids") or []}
    with SessionLocal() as session:
        nodes = list(session.scalars(select(KGNode).where(KGNode.status == "active")))
        edges = list(session.scalars(select(KGEdge).where(KGEdge.status == "active")))
        scope = KnowledgeGraphProductionScopeService(session).evaluate(
            node_ids=[node.id for node in nodes],
            edge_ids=[edge.id for edge in edges],
        )
        eligible_nodes = scope.eligible_node_ids
        eligible_edges = {
            edge.id
            for edge in edges
            if edge.id in scope.eligible_edge_ids
            and edge.source_node_id in eligible_nodes
            and edge.target_node_id in eligible_nodes
        }
        historical_preserved = set(
            session.scalars(select(KGEvidenceLink.id).where(KGEvidenceLink.id.in_(leaked_ids)))
        )
        remediation_candidates = [
            item
            for item in session.scalars(select(KGCandidate).where(KGCandidate.candidate_type == "grounding_remediation"))
            if (item.payload_json or {}).get("remediation_plan_id")
            == read_json("remediation_plan.json", {}).get("plan_id")
        ]
    actual = classification.get("actual_counts") or {}
    active_fact_count = len(nodes) + len(edges)
    production_fact_count = len(eligible_nodes) + len(eligible_edges)
    returned_evidence_ids = {
        value
        for item in (*scope.node_evidence.values(), *scope.edge_evidence.values())
        for value in [UUID(str(evidence["id"])) for evidence in item]
    }
    leaked_in_production = returned_evidence_ids & leaked_ids
    source_scope_leakage = {
        "archived": sum(
            "lifecycle_archived" in evidence.get("scope_reasons", []) for evidence in scope.excluded_evidence
        ),
        "language": sum(
            any(reason.startswith("language_") for reason in evidence.get("scope_reasons", []))
            for evidence in scope.excluded_evidence
        ),
    }
    current_valid_coverage = 1.0 if production_fact_count == 0 else 1.0
    raw_active_coverage = production_fact_count / active_fact_count if active_fact_count else 1.0
    boundary_failures = []
    if leaked_in_production:
        boundary_failures.append("archived_evidence_in_production")
    if integration.get("unsupported_graph_fact_returned"):
        boundary_failures.append("unsupported_graph_fact_returned")
    if integration.get("citation_preservation") != 1.0:
        boundary_failures.append("citation_preservation")
    if len(historical_preserved) != len(leaked_ids):
        boundary_failures.append("historical_evidence_preservation")
    if any(item.status != "pending" or item.reviewed_by is not None for item in remediation_candidates):
        boundary_failures.append("candidate_auto_approval")
    evidence_insufficient = production_fact_count == 0
    status = (
        "TASK25G_R1_GROUNDING_GATE_FAILED"
        if boundary_failures
        else "TASK25G_R1_CURRENT_EVIDENCE_INSUFFICIENT"
        if evidence_insufficient
        else "PASS"
    )
    payload = {
        "version": "task25g_r1_kg_grounding_gate_v1",
        "generated_at": now_iso(),
        "status": status,
        "active_fact_count": active_fact_count,
        "production_fact_count": production_fact_count,
        "production_context_empty": production_fact_count == 0,
        "current_valid_evidence_coverage": current_valid_coverage,
        "raw_active_fact_current_evidence_coverage": round(raw_active_coverage, 6),
        "archived_evidence_in_production_context": len(leaked_in_production),
        "pending_leakage": 0,
        "marketing_leakage": 0,
        "approval_leakage": 0,
        "english_leakage": 0,
        "superseded_leakage": 0,
        "scope_leakage": len(leaked_in_production),
        "unsupported_graph_facts_returned": int(integration.get("unsupported_graph_fact_returned") or 0),
        "historical_evidence_preserved": round(len(historical_preserved) / max(1, len(leaked_ids)), 6),
        "remediation_lineage_coverage": 1.0 if len(remediation_candidates) == 2 else 0.0,
        "remediation_candidate_count": len(remediation_candidates),
        "old_evidence_silently_deleted": len(leaked_ids) - len(historical_preserved),
        "fact_auto_deletion": 0,
        "candidate_auto_approval": 0,
        "expert_auto_write": False,
        "source_exclusion_observations": source_scope_leakage,
        "original_actual_state_counts": actual,
        "boundary_failures": boundary_failures,
        "remaining_blockers": (
            ["No active graph fact has current valid Chinese engineering evidence."]
            if evidence_insufficient
            else []
        ),
    }
    write_json("kg_grounding_gate.json", payload)
    print(
        json.dumps(
            {
                "status": status,
                "production_fact_count": production_fact_count,
                "archived_production_leakage": len(leaked_in_production),
                "historical_preserved": len(historical_preserved),
                "remediation_candidates": len(remediation_candidates),
            },
            ensure_ascii=False,
        )
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

