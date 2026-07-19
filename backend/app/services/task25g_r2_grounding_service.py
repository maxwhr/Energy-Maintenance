from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from app.services.task25g_r2_hashing import stable_hash


DIRECT_SUPPORT_LEVELS = {"DIRECT_EXACT_SUPPORT", "DIRECT_MULTI_SOURCE_SUPPORT"}
ALLOWED_GROUNDING_OPERATIONS = {
    "CREATE_CURRENT_EVIDENCE_LINK",
    "REUSE_CURRENT_EVIDENCE_LINK",
    "MARK_HISTORICAL_EVIDENCE_NON_PRODUCTION",
    "CREATE_MANUAL_REVIEW_CANDIDATE",
}


class Task25GR2GroundingService:
    """Builds deterministic manifests and validates the non-vacuous grounding gate."""

    CORE_VERSION = "task25g_r2_production_core_fact_manifest_v1"
    PLAN_VERSION = "task25g_r2_grounding_plan_v1"

    @staticmethod
    def eligible_items(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        eligible: list[dict[str, Any]] = []
        for result in results:
            fact = result["fact"]
            candidate = next(
                (
                    item
                    for item in result.get("candidates") or []
                    if item.get("support_level") in DIRECT_SUPPORT_LEVELS
                    and item.get("automatic_binding_eligible")
                    and item.get("document_current")
                    and item.get("engineering_approved")
                    and item.get("locator_valid")
                    and item.get("scope_valid")
                    and not item.get("conflict")
                    and not item.get("entity_conflict")
                ),
                None,
            )
            if candidate is None:
                continue
            eligible.append(
                {
                    "fact_id": fact["fact_id"],
                    "fact_kind": fact["fact_kind"],
                    "fact_category": fact["fact_category"],
                    "relation_type": fact.get("relation_type"),
                    "identity_hash": fact["identity_hash"],
                    "candidate_id": candidate["candidate_id"],
                    "candidate_hash": candidate["candidate_hash"],
                    "support_level": candidate["support_level"],
                    "source_kind": candidate["source_kind"],
                    "document_id": candidate["document_id"],
                    "chunk_id": candidate["chunk_id"],
                    "semantic_unit_id": candidate["semantic_unit_id"],
                    "source_locator": candidate["source_locator"],
                    "equivalence": candidate["equivalence"],
                }
            )
        return sorted(eligible, key=lambda item: item["fact_id"])

    @staticmethod
    def evaluate_gate(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
        values = list(items)
        nodes = [item for item in values if item["fact_kind"] == "NODE"]
        edges = [item for item in values if item["fact_kind"] == "EDGE"]
        relation_types = sorted({item["relation_type"] for item in edges if item.get("relation_type")})
        categories = sorted({item["fact_category"] for item in values})
        evidence_candidates = {item["candidate_id"] for item in values}
        checks = {
            "grounded_facts_at_least_10": len(values) >= 10,
            "grounded_nodes_at_least_5": len(nodes) >= 5,
            "grounded_edges_at_least_5": len(edges) >= 5,
            "relation_types_at_least_2": len(relation_types) >= 2,
            "current_evidence_at_least_10": len(evidence_candidates) >= 10,
            "node_and_edge_non_empty": bool(nodes and edges),
            "categories_at_least_3": len(categories) >= 3,
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "eligible_fact_count": len(values),
            "eligible_node_count": len(nodes),
            "eligible_edge_count": len(edges),
            "relation_types": relation_types,
            "relation_type_count": len(relation_types),
            "current_evidence_candidate_count": len(evidence_candidates),
            "categories": categories,
            "category_count": len(categories),
            "support_levels": dict(sorted(Counter(item["support_level"] for item in values).items())),
        }

    @classmethod
    def build_manifest(
        cls,
        *,
        results: Iterable[dict[str, Any]],
        corpus_sha256: str,
        matcher_version: str,
        relation_matrix_version: str,
    ) -> dict[str, Any]:
        facts = cls.eligible_items(results)
        gate = cls.evaluate_gate(facts)
        core = {
            "version": cls.CORE_VERSION,
            "corpus_sha256": corpus_sha256,
            "matcher_version": matcher_version,
            "relation_matrix_version": relation_matrix_version,
            "facts": facts,
            "gate": gate,
        }
        return {
            **core,
            "status": "PRODUCTION_CORE_GATE_PASS"
            if gate["passed"]
            else "TASK25G_R2_CURRENT_CHINESE_GRAPH_EVIDENCE_INSUFFICIENT",
            "manifest_sha256": stable_hash(core),
        }

    @classmethod
    def build_plan(
        cls,
        *,
        manifest: dict[str, Any],
        all_facts: Iterable[dict[str, Any]],
        historical_evidence_ids: Iterable[str | dict[str, Any]],
    ) -> dict[str, Any]:
        eligible = {item["fact_id"]: item for item in manifest.get("facts") or []}
        operations: list[dict[str, Any]] = []
        for item in eligible.values():
            desired = {
                "fact_id": item["fact_id"],
                "candidate_id": item["candidate_id"],
                "source_type": "task25g_r2_current_chinese_grounding",
                "document_id": item["document_id"],
                "chunk_id": item["chunk_id"],
                "semantic_unit_id": item["semantic_unit_id"],
                "source_locator": item["source_locator"],
                "grounding_status": "GROUNDED_CURRENT",
            }
            operations.append(
                {
                    "operation": "CREATE_CURRENT_EVIDENCE_LINK",
                    "fact_id": item["fact_id"],
                    "source_document_id": item["document_id"],
                    "source_chunk_id": item["chunk_id"],
                    "source_semantic_unit_id": item["semantic_unit_id"],
                    "source_locator": item["source_locator"],
                    "support_level": item["support_level"],
                    "old_state_hash": stable_hash({"fact_identity": item["identity_hash"], "evidence": None}),
                    "new_state_hash": stable_hash(desired),
                    "equivalence_evidence": item["equivalence"],
                    "reversible": True,
                    "requires_explicit_apply": True,
                }
            )
        historical_rows: dict[str, dict[str, Any]] = {}
        for raw in historical_evidence_ids:
            row = raw if isinstance(raw, dict) else {"evidence_id": str(raw)}
            historical_rows[str(row["evidence_id"])] = row
        for evidence_id, row in sorted(historical_rows.items()):
            fact_id = (
                f"node:{row['node_id']}"
                if row.get("node_id")
                else f"edge:{row['edge_id']}" if row.get("edge_id") else None
            )
            operations.append(
                {
                    "operation": "MARK_HISTORICAL_EVIDENCE_NON_PRODUCTION",
                    "fact_id": fact_id,
                    "source_document_id": row.get("document_id"),
                    "source_chunk_id": row.get("chunk_id"),
                    "source_semantic_unit_id": None,
                    "source_locator": None,
                    "support_level": "HISTORICAL_ONLY",
                    "old_state_hash": stable_hash({"evidence_id": evidence_id, "preserved": True}),
                    "new_state_hash": stable_hash(
                        {"evidence_id": evidence_id, "preserved": True, "production_eligible": False}
                    ),
                    "equivalence_evidence": {
                        "evidence_id": evidence_id,
                        "source_type": row.get("source_type"),
                        "scope_excluded": True,
                    },
                    "reversible": True,
                    "requires_explicit_apply": False,
                }
            )
        for fact in sorted(all_facts, key=lambda value: value["fact_id"]):
            if fact["fact_id"] in eligible:
                continue
            desired = {
                "candidate_type": "task25g_r2_current_source_review",
                "target_fact_id": fact["fact_id"],
                "status": "pending",
                "production_grounding_status": "UNSUPPORTED_CURRENT_SOURCE",
                "expert_verified": False,
            }
            operations.append(
                {
                    "operation": "CREATE_MANUAL_REVIEW_CANDIDATE",
                    "fact_id": fact["fact_id"],
                    "source_document_id": None,
                    "source_chunk_id": None,
                    "source_semantic_unit_id": None,
                    "source_locator": None,
                    "support_level": "REQUIRES_REVIEW",
                    "old_state_hash": stable_hash({"fact_identity": fact["identity_hash"], "candidate": None}),
                    "new_state_hash": stable_hash(desired),
                    "equivalence_evidence": {"reason": "no direct current Chinese support"},
                    "reversible": True,
                    "requires_explicit_apply": True,
                }
            )
        if any(item["operation"] not in ALLOWED_GROUNDING_OPERATIONS for item in operations):
            raise ValueError("grounding plan contains a forbidden operation")
        plan_core = {
            "version": cls.PLAN_VERSION,
            "core_manifest_sha256": manifest["manifest_sha256"],
            "core_gate_passed": bool((manifest.get("gate") or {}).get("passed")),
            "operations": operations,
            "boundaries": {
                "fact_deletes": 0,
                "fact_updates": 0,
                "evidence_deletes": 0,
                "document_updates": 0,
                "chunk_updates": 0,
                "semantic_unit_updates": 0,
                "vector_writes": 0,
                "embedding_writes": 0,
                "candidate_auto_approvals": 0,
                "expert_auto_writes": 0,
            },
        }
        return {
            **plan_core,
            "status": "DRY_RUN_READY" if plan_core["core_gate_passed"] else "TASK25G_R2_GROUNDING_PLAN_REJECTED",
            "plan_sha256": stable_hash(plan_core),
        }

    @staticmethod
    def validate_plan(plan: dict[str, Any]) -> None:
        if not plan.get("operations"):
            raise ValueError("grounding plan is empty")
        forbidden = {
            item.get("operation")
            for item in plan["operations"]
            if item.get("operation") not in ALLOWED_GROUNDING_OPERATIONS
        }
        if forbidden:
            raise ValueError(f"forbidden grounding operations: {sorted(forbidden)}")
        boundaries = plan.get("boundaries") or {}
        if any(int(boundaries.get(key) or 0) for key in boundaries):
            raise ValueError("grounding plan violates immutable-data boundaries")
