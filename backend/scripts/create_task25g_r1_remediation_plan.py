from __future__ import annotations

import json
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import select

from task25g_r1_common import now_iso, read_json, sha256_value, write_csv, write_json


CSV_FIELDS = [
    "operation",
    "target_id",
    "old_state_hash",
    "new_state_hash",
    "reason",
    "source_evidence",
    "reversible",
    "approval_required",
]


def evidence_state(evidence: Any) -> dict[str, Any]:
    return {
        "id": str(evidence.id),
        "node_id": str(evidence.node_id) if evidence.node_id else None,
        "edge_id": str(evidence.edge_id) if evidence.edge_id else None,
        "source_type": evidence.source_type,
        "source_id": str(evidence.source_id) if evidence.source_id else None,
        "document_id": str(evidence.document_id) if evidence.document_id else None,
        "chunk_id": str(evidence.chunk_id) if evidence.chunk_id else None,
        "created_at": evidence.created_at,
    }


def fact_state(fact: Any, fact_type: str) -> dict[str, Any]:
    if fact_type == "node":
        return {
            "id": str(fact.id),
            "fact_type": "node",
            "node_type": fact.node_type,
            "status": fact.status,
            "manufacturer": fact.manufacturer,
            "product_series": fact.product_series,
        }
    return {
        "id": str(fact.id),
        "fact_type": "edge",
        "source_node_id": str(fact.source_node_id),
        "target_node_id": str(fact.target_node_id),
        "relation_type": fact.relation_type,
        "status": fact.status,
    }


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGEdge, KGEvidenceLink, KGNode

    forensics = read_json("archived_evidence_forensics.json", [])
    equivalence = read_json("evidence_equivalence.json", {})
    status_by_evidence = {
        str(item["evidence_id"]): item.get("status")
        for item in equivalence.get("items") or []
    }
    operations = []
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    with SessionLocal() as session:
        for item in forensics:
            evidence = session.get(KGEvidenceLink, UUID(item["evidence_id"]))
            if evidence is None:
                raise RuntimeError(f"evidence missing while planning: {item['evidence_id']}")
            old_state = evidence_state(evidence)
            new_state = {
                **old_state,
                "production_scope_status": "HISTORICAL_NON_PRODUCTION",
                "production_exclusion_reason": "archived_or_non_chinese_source",
            }
            operations.append(
                {
                    "operation": "EXCLUDE_EVIDENCE_FROM_PRODUCTION_BY_SOURCE_SCOPE",
                    "target_id": str(evidence.id),
                    "target_type": "kg_evidence_link",
                    "old_state_hash": sha256_value(old_state),
                    "new_state_hash": sha256_value(new_state),
                    "reason": "historical maintenance evidence has no explicit current Chinese successor",
                    "source_evidence": [str(evidence.id)],
                    "reversible": True,
                    "approval_required": False,
                    "database_mutation_required": False,
                    "equivalence_status": status_by_evidence.get(str(evidence.id), "NOT_FOUND"),
                }
            )
            fact_type = "node" if evidence.node_id else "edge"
            fact_id = str(evidence.node_id or evidence.edge_id)
            grouped[(fact_type, fact_id)].append(str(evidence.id))

        for (fact_type, fact_id), evidence_ids in sorted(grouped.items()):
            fact = session.get(KGNode if fact_type == "node" else KGEdge, UUID(fact_id))
            if fact is None:
                raise RuntimeError(f"fact missing while planning: {fact_type}:{fact_id}")
            old_state = fact_state(fact, fact_type)
            desired = {
                "target_type": fact_type,
                "target_id": fact_id,
                "candidate_type": "grounding_remediation",
                "status": "pending",
                "production_grounding_status": "UNSUPPORTED_CURRENT_SOURCE",
                "source_evidence_ids": sorted(evidence_ids),
                "expert_verified": False,
            }
            operations.append(
                {
                    "operation": "CREATE_KG_REMEDIATION_CANDIDATE",
                    "target_id": fact_id,
                    "target_type": fact_type,
                    "old_state_hash": sha256_value(old_state),
                    "new_state_hash": sha256_value(desired),
                    "reason": "active fact has historical evidence only and requires an explicit current Chinese source",
                    "source_evidence": sorted(evidence_ids),
                    "reversible": True,
                    "approval_required": True,
                    "database_mutation_required": True,
                    "desired_candidate": desired,
                }
            )

    plan_core = {
        "version": "task25g_r1_remediation_plan_v1",
        "operations": operations,
        "boundaries": {
            "fact_updates": 0,
            "evidence_deletes": 0,
            "evidence_rebinds": 0,
            "candidate_auto_approvals": 0,
            "expert_auto_writes": 0,
            "document_updates": 0,
            "chunk_updates": 0,
            "vector_writes": 0,
            "embedding_writes": 0,
        },
    }
    plan_id = sha256_value(plan_core)
    payload = {
        **plan_core,
        "generated_at": now_iso(),
        "status": "DRY_RUN_READY",
        "plan_id": plan_id,
        "operation_count": len(operations),
        "database_mutation_count": sum(bool(item["database_mutation_required"]) for item in operations),
        "approval_required_count": sum(bool(item["approval_required"]) for item in operations),
    }
    write_json("remediation_plan.json", payload)
    write_csv("remediation_plan.csv", operations, CSV_FIELDS)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "plan_id": plan_id,
                "operations": payload["operation_count"],
                "candidate_writes": payload["database_mutation_count"],
                "evidence_rebinds": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

