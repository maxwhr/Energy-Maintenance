from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import or_, select

from task25g_r1_common import TASK25G_RUNTIME, now_iso, sha256_text, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGEdge, KGEvidenceLink, KGNode
    from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService
    from app.services.knowledge_graph_service import KnowledgeGraphService

    task25g_integrity = json.loads((TASK25G_RUNTIME / "kg_integrity.json").read_text(encoding="utf-8"))
    orphan_ids = [
        UUID(item["node_id"])
        for item in task25g_integrity.get("issues") or []
        if item.get("problem_type") == "orphan_active_node" and item.get("node_id")
    ]
    output = []
    with SessionLocal() as session:
        scope_service = KnowledgeGraphProductionScopeService(session)
        for node_id in orphan_ids:
            node = session.get(KGNode, node_id)
            if not node:
                output.append({"node_id": str(node_id), "classification": "UNKNOWN", "reason": "node_missing"})
                continue
            edges = list(
                session.scalars(
                    select(KGEdge).where(
                        KGEdge.status == "active",
                        or_(KGEdge.source_node_id == node.id, KGEdge.target_node_id == node.id),
                    )
                )
            )
            evidence_ids = [
                str(value)
                for value in session.scalars(
                    select(KGEvidenceLink.id)
                    .where(KGEvidenceLink.node_id == node.id)
                    .order_by(KGEvidenceLink.id.asc())
                )
            ]
            scope = scope_service.evaluate(node_ids=[node.id])
            production_evidence_ids = scope.evidence_ids_for_node(node.id)
            source_type = str(node.source_type or "").lower()
            if edges:
                classification = "STRUCTURAL_NODE"
                reason = "active_edges_exist_after_original_snapshot"
            elif production_evidence_ids and node.node_type in {"manufacturer", "product_series"}:
                classification = "LEGAL_ROOT_NODE"
                reason = "root_taxonomy_node_with_current_evidence"
            elif production_evidence_ids:
                classification = "MISSING_EDGE"
                reason = "current_supported_fact_has_no_active_edge"
            elif "test" in source_type or "probe" in source_type:
                classification = "TEST_RESIDUE"
                reason = "test_source_without_current_evidence"
            elif evidence_ids:
                classification = "HISTORICAL_ONLY"
                reason = "only_historical_or_invalid_source_evidence"
            else:
                classification = "UNSUPPORTED_FACT"
                reason = "no_evidence_and_no_active_edge"
            try:
                context = KnowledgeGraphService(session).business_context(question=node.canonical_name, limit=20)
                returned = any(str(item.get("id")) == str(node.id) for item in context.get("kg_nodes") or [])
            except Exception as exc:  # noqa: BLE001 - audit reports runtime boundary.
                returned = False
                reason = f"{reason};context_error={exc.__class__.__name__}"
            output.append(
                {
                    "node_id": str(node.id),
                    "node_type": node.node_type,
                    "canonical_name_hash": sha256_text(node.canonical_name),
                    "source_type": node.source_type,
                    "source_id": str(node.source_id) if node.source_id else None,
                    "active_edge_count": len(edges),
                    "source_evidence_ids": evidence_ids,
                    "current_valid_evidence_ids": production_evidence_ids,
                    "production_context_returned": returned,
                    "classification": classification,
                    "reason": reason,
                    "automatic_delete": False,
                    "automatic_edge_write": False,
                }
            )
    payload = {
        "version": "task25g_r1_orphan_node_v1",
        "generated_at": now_iso(),
        "status": "PASS"
        if output and all(item["classification"] != "UNKNOWN" and not item["production_context_returned"] for item in output)
        else "FAIL",
        "orphan_count": len(output),
        "items": output,
    }
    write_json("orphan_node.json", payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "classifications": [item["classification"] for item in output],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
