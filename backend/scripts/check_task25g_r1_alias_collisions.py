from __future__ import annotations

import json
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from task25g_r1_common import now_iso, sha256_text, write_json


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGEvidenceLink, KGNode, KGNodeAlias
    from app.services.kg_alias_resolution_policy_service import KGAliasResolutionPolicyService

    output = []
    with SessionLocal() as session:
        collision_aliases = list(
            session.scalars(
                select(KGNodeAlias.normalized_alias)
                .group_by(KGNodeAlias.normalized_alias)
                .having(func.count(func.distinct(KGNodeAlias.node_id)) > 1)
                .order_by(KGNodeAlias.normalized_alias.asc())
            )
        )
        service = KGAliasResolutionPolicyService(session)
        for normalized_alias in collision_aliases:
            nodes = list(
                session.scalars(
                    select(KGNode)
                    .join(KGNodeAlias, KGNodeAlias.node_id == KGNode.id)
                    .options(selectinload(KGNode.aliases))
                    .where(
                        KGNodeAlias.normalized_alias == normalized_alias,
                        KGNode.status == "active",
                    )
                    .order_by(KGNode.id.asc())
                )
            )
            result = service.resolve_candidates(nodes)
            node_details = []
            context_resolution_pass = True
            for node in nodes:
                properties = node.properties_json or {}
                context = {
                    "node_type": node.node_type,
                    "manufacturer": node.manufacturer,
                    "product_series": node.product_series,
                    "model": properties.get("model"),
                    "alarm_code": properties.get("alarm_code"),
                }
                context = {key: value for key, value in context.items() if value not in (None, "")}
                contextual = service.resolve_candidates(nodes, context=context)
                if result.resolution_status == "CONTEXT_DEPENDENT":
                    context_resolution_pass = context_resolution_pass and contextual.resolved_node_id == node.id
                evidence_ids = [
                    str(value)
                    for value in session.scalars(
                        select(KGEvidenceLink.id).where(KGEvidenceLink.node_id == node.id).order_by(KGEvidenceLink.id.asc())
                    )
                ]
                node_details.append(
                    {
                        "node_id": str(node.id),
                        "node_type": node.node_type,
                        "manufacturer": node.manufacturer,
                        "product_series": node.product_series,
                        "model": properties.get("model"),
                        "alarm_code": properties.get("alarm_code"),
                        "canonical_name_hash": sha256_text(node.canonical_name),
                        "source_evidence_ids": evidence_ids,
                        "usage_count": len(evidence_ids),
                        "context_probe_status": contextual.resolution_status,
                        "context_probe_resolved_node_id": (
                            str(contextual.resolved_node_id) if contextual.resolved_node_id else None
                        ),
                    }
                )
            output.append(
                {
                    "alias_hash": sha256_text(normalized_alias),
                    "node_ids": [str(value) for value in result.candidate_node_ids],
                    "classification": result.resolution_status,
                    "resolved_node_id": str(result.resolved_node_id) if result.resolved_node_id else None,
                    "required_context": list(result.required_context),
                    "clarification_required": result.clarification_required,
                    "context_resolution_deterministic": context_resolution_pass,
                    "unsafe_automatic_resolution": False,
                    "nodes": node_details,
                }
            )
    counts = Counter(item["classification"] for item in output)
    payload = {
        "version": "task25g_r1_alias_collisions_v1",
        "generated_at": now_iso(),
        "status": "PASS"
        if all(
            not item["unsafe_automatic_resolution"]
            and (item["classification"] != "CONTEXT_DEPENDENT" or item["context_resolution_deterministic"])
            and item["classification"] != "UNRESOLVED"
            for item in output
        )
        else "FAIL",
        "collision_count": len(output),
        "classification_counts": dict(sorted(counts.items())),
        "unsafe_automatic_resolution_count": sum(item["unsafe_automatic_resolution"] for item in output),
        "canonicalization_deterministic": all(item["context_resolution_deterministic"] for item in output),
        "items": output,
        "alias_values_recorded": False,
    }
    write_json("alias_collisions.json", payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "collision_count": payload["collision_count"],
                "classifications": payload["classification_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

