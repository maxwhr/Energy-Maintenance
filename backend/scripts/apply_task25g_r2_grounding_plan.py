from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import select

from task25g_r2_common import now_iso, read_json, sha256_value, write_json


SOURCE_TYPE = "task25g_r2_current_chinese_grounding"


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the frozen Task 25G-R2 grounding plan")
    parser.add_argument("--apply-approved-engineering-grounding", action="store_true")
    return parser.parse_args()


def _manifest_hash(manifest: dict[str, Any]) -> str:
    core = {
        key: manifest[key]
        for key in (
            "version",
            "corpus_sha256",
            "matcher_version",
            "relation_matrix_version",
            "facts",
            "gate",
        )
    }
    return sha256_value(core)


def _verify_frozen_state(session: Any, manifest: dict[str, Any], plan: dict[str, Any]) -> dict[str, int]:
    from app.models import KGEvidenceLink
    from app.services.knowledge_graph_fact_identity_service import KnowledgeGraphFactIdentityService
    from app.services.task25g_r2_grounding_service import Task25GR2GroundingService

    Task25GR2GroundingService.validate_plan(plan)
    if _manifest_hash(manifest) != manifest.get("manifest_sha256"):
        raise RuntimeError("production core manifest SHA-256 mismatch")
    if plan.get("core_manifest_sha256") != manifest.get("manifest_sha256"):
        raise RuntimeError("grounding plan references a different core manifest")
    current_facts = {
        item["fact_id"]: item for item in KnowledgeGraphFactIdentityService.list_active_facts(session)
    }
    checked_facts = 0
    checked_history = 0
    for operation in plan["operations"]:
        fact_id = operation.get("fact_id")
        if fact_id:
            fact = current_facts.get(fact_id)
            if fact is None:
                raise RuntimeError(f"active fact drifted or disappeared: {fact_id}")
            checked_facts += 1
        if operation["operation"] == "MARK_HISTORICAL_EVIDENCE_NON_PRODUCTION":
            evidence_id = UUID(operation["equivalence_evidence"]["evidence_id"])
            if session.get(KGEvidenceLink, evidence_id) is None:
                raise RuntimeError(f"historical evidence was not preserved: {evidence_id}")
            checked_history += 1
    return {"fact_state_checks": checked_facts, "historical_evidence_checks": checked_history}


def _find_semantic_anchor(session: Any, semantic_unit_id: str) -> Any:
    from app.models import MaintenanceSemanticAnchor

    anchors = session.scalars(
        select(MaintenanceSemanticAnchor).where(
            MaintenanceSemanticAnchor.semantic_representation_version
            == "task25b_r3_dev_r5_semantic_unit_v2"
        )
    )
    for anchor in anchors:
        unit = (anchor.semantic_fields or {}).get("semantic_unit") or {}
        current_id = unit.get("semantic_unit_id") or (anchor.semantic_fields or {}).get("semantic_unit_id")
        if str(current_id) == semantic_unit_id:
            return anchor
    raise RuntimeError(f"semantic unit not found: {semantic_unit_id}")


def _current_evidence(session: Any, operation: dict[str, Any]) -> Any | None:
    from app.models import KGEvidenceLink

    source_id = uuid5(NAMESPACE_URL, f"task25g-r2:{operation['source_semantic_unit_id']}")
    kind, raw_id = operation["fact_id"].split(":", 1)
    fact_filter = KGEvidenceLink.node_id == UUID(raw_id) if kind == "node" else KGEvidenceLink.edge_id == UUID(raw_id)
    return session.scalar(
        select(KGEvidenceLink)
        .where(
            fact_filter,
            KGEvidenceLink.source_type == SOURCE_TYPE,
            KGEvidenceLink.source_id == source_id,
        )
        .limit(1)
    )


def _write_operation_log(session: Any, operation: dict[str, Any], plan_hash: str) -> bool:
    from app.models import OperationLog

    trace_id = "kg-r2-" + sha256_value(
        [plan_hash, operation["operation"], operation.get("fact_id"), operation.get("source_semantic_unit_id")]
    )[:48]
    if session.scalar(select(OperationLog.id).where(OperationLog.trace_id == trace_id).limit(1)):
        return False
    session.add(
        OperationLog(
            module="knowledge_graph",
            action="task25g_r2_engineering_grounding",
            target_type="graph_fact",
            target_id=operation.get("fact_id"),
            operator="engineering_grounding",
            request_id=plan_hash[:64],
            trace_id=trace_id,
            detail={
                "operation": operation["operation"],
                "source_semantic_unit_id": operation.get("source_semantic_unit_id"),
                "source_locator": operation.get("source_locator"),
                "support_level": operation.get("support_level"),
                "old_state_hash": operation["old_state_hash"],
                "new_state_hash": operation["new_state_hash"],
                "expert_verified": False,
                "fact_content_changed": False,
            },
        )
    )
    return True


def _apply(session: Any, manifest: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    from app.models import KGEvidenceLink

    if not (manifest.get("gate") or {}).get("passed") or not plan.get("core_gate_passed"):
        raise RuntimeError("Task 25G-R2 production core gate is not satisfied; apply is forbidden")
    created = 0
    reused = 0
    logs = 0
    with session.begin():
        checks = _verify_frozen_state(session, manifest, plan)
        for operation in plan["operations"]:
            if operation["operation"] not in {"CREATE_CURRENT_EVIDENCE_LINK", "REUSE_CURRENT_EVIDENCE_LINK"}:
                continue
            evidence = _current_evidence(session, operation)
            if evidence is None:
                anchor = _find_semantic_anchor(session, operation["source_semantic_unit_id"])
                unit = (anchor.semantic_fields or {}).get("semantic_unit") or {}
                kind, raw_id = operation["fact_id"].split(":", 1)
                evidence = KGEvidenceLink(
                    node_id=UUID(raw_id) if kind == "node" else None,
                    edge_id=UUID(raw_id) if kind == "edge" else None,
                    source_type=SOURCE_TYPE,
                    source_id=uuid5(NAMESPACE_URL, f"task25g-r2:{operation['source_semantic_unit_id']}"),
                    document_id=UUID(operation["source_document_id"]),
                    chunk_id=UUID(operation["source_chunk_id"]),
                    evidence_text=str(unit.get("canonical_evidence") or anchor.anchor_text or "")[:8000],
                    confidence=1.0,
                )
                session.add(evidence)
                session.flush()
                created += 1
            else:
                reused += 1
            logs += int(_write_operation_log(session, operation, plan["plan_sha256"]))
        if created + reused != len(manifest.get("facts") or []):
            raise RuntimeError("not every frozen eligible fact received a current Evidence link")
    return {
        **checks,
        "status": "APPLY_PASS",
        "created_current_evidence": created,
        "reused_current_evidence": reused,
        "operation_log_writes": logs,
        "transaction_committed": True,
    }


def main() -> int:
    args = _args()
    manifest = read_json("production_core_fact_manifest.json", {})
    plan = read_json("grounding_plan.json", {})
    if not manifest or not plan:
        raise SystemExit("Task 25G-R2 production core manifest or grounding plan is missing")

    from app.core.database import SessionLocal

    with SessionLocal() as session:
        checks = _verify_frozen_state(session, manifest, plan)
        if args.apply_approved_engineering_grounding:
            if not (manifest.get("gate") or {}).get("passed"):
                result = {
                    "version": "task25g_r2_grounding_execution_v1",
                    "generated_at": now_iso(),
                    "status": "APPLY_REJECTED_CORE_GATE",
                    "apply_flag": True,
                    **checks,
                    "database_writes": 0,
                    "transaction_committed": False,
                }
            else:
                applied = _apply(session, manifest, plan)
                result = {
                    "version": "task25g_r2_grounding_execution_v1",
                    "generated_at": now_iso(),
                    "apply_flag": True,
                    **applied,
                    "database_writes": applied["created_current_evidence"] + applied["operation_log_writes"],
                }
        else:
            result = {
                "version": "task25g_r2_grounding_execution_v1",
                "generated_at": now_iso(),
                "status": "DRY_RUN_PASS"
                if (manifest.get("gate") or {}).get("passed")
                else "DRY_RUN_GATE_BLOCKED",
                "apply_flag": False,
                **checks,
                "database_writes": 0,
                "created_current_evidence": 0,
                "reused_current_evidence": 0,
                "operation_log_writes": 0,
                "transaction_committed": False,
            }
    result.update(
        {
            "historical_evidence_deleted": 0,
            "fact_updates": 0,
            "document_updates": 0,
            "chunk_updates": 0,
            "semantic_unit_updates": 0,
            "vector_writes": 0,
            "embedding_writes": 0,
            "expert_auto_write": False,
        }
    )
    write_json("grounding_execution.json", result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] != "APPLY_REJECTED_CORE_GATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())

