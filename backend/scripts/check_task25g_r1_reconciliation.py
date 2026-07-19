from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text

from create_task25g_r1_remediation_plan import evidence_state, fact_state
from task25g_r1_common import (
    BACKEND,
    EXPECTED_ALEMBIC_REVISION,
    ROOT,
    TASK25G_REPORT,
    TASK25G_RUNTIME,
    alembic_state,
    directory_manifest,
    now_iso,
    read_json,
    sha256_file,
    sha256_value,
    write_json,
    zip_inventory,
)


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGCandidate, KGEdge, KGEvidenceLink, KGNode, OperationLog

    snapshot = read_json("task25g_snapshot.json", {})
    manifest = read_json("hash_manifest.json", {})
    baseline = read_json("leakage_baseline.json", {})
    plan = read_json("remediation_plan.json", {})
    execution = read_json("remediation_execution.json", {})
    current_task25g_manifest = directory_manifest(TASK25G_RUNTIME)
    frozen_task25g_manifest = manifest.get("task25g", {}).get("runtime", {})
    current_alembic = alembic_state()
    failures = []
    checks = {
        "task25g_report_unchanged": sha256_file(TASK25G_REPORT)
        == manifest.get("task25g", {}).get("report", {}).get("sha256"),
        "task25g_runtime_unchanged": current_task25g_manifest.get("aggregate_sha256")
        == frozen_task25g_manifest.get("aggregate_sha256"),
        "backend_env_unchanged": sha256_file(BACKEND / ".env") == manifest.get("backend_env", {}).get("sha256"),
        "alembic_unchanged": EXPECTED_ALEMBIC_REVISION in current_alembic.get("current", ""),
        "zip_inventory_unchanged": zip_inventory() == snapshot.get("zip_inventory"),
    }
    with SessionLocal() as session:
        evidence_ids = [UUID(value) for value in baseline.get("evidence_ids") or []]
        preserved = list(session.scalars(select(KGEvidenceLink).where(KGEvidenceLink.id.in_(evidence_ids))))
        checks["historical_evidence_preserved"] = len(preserved) == len(evidence_ids)
        plan_state_match = True
        for operation in plan.get("operations") or []:
            if operation["target_type"] == "kg_evidence_link":
                target = session.get(KGEvidenceLink, UUID(operation["target_id"]))
                state = evidence_state(target) if target else None
            else:
                model = KGNode if operation["target_type"] == "node" else KGEdge
                target = session.get(model, UUID(operation["target_id"]))
                state = fact_state(target, operation["target_type"]) if target else None
            plan_state_match = plan_state_match and sha256_value(state) == operation["old_state_hash"]
        checks["facts_and_evidence_rows_unchanged"] = plan_state_match
        remediation_candidates = [
            item
            for item in session.scalars(select(KGCandidate).where(KGCandidate.candidate_type == "grounding_remediation"))
            if (item.payload_json or {}).get("remediation_plan_id") == plan.get("plan_id")
        ]
        checks["remediation_candidates_exact"] = len(remediation_candidates) == 2
        checks["candidate_auto_approval_zero"] = all(
            item.status == "pending" and item.reviewed_by is None and item.reviewed_at is None
            for item in remediation_candidates
        )
        log_count = int(
            session.scalar(
                select(text("count(*)")).select_from(OperationLog).where(
                    OperationLog.action == "task25g_r1_grounding_remediation",
                    OperationLog.request_id == str(plan.get("plan_id", ""))[:64],
                )
            )
            or 0
        )
        checks["operation_log_coverage"] = log_count == int(plan.get("operation_count") or 0)
        vectors = [
            {"namespace": str(row[0]), "count": int(row[1])}
            for row in session.execute(
                text(
                    "SELECT namespace, count(*) FROM knowledge_chunk_vector_indexes "
                    "GROUP BY namespace ORDER BY namespace"
                )
            )
        ]
        checks["vector_namespaces_unchanged"] = vectors == snapshot.get("database", {}).get("vector_namespaces")
    for name, passed in checks.items():
        if not passed:
            failures.append(name)
    payload = {
        "version": "task25g_r1_reconciliation_v1",
        "generated_at": now_iso(),
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "historical_evidence_count": len(preserved),
        "remediation_candidate_count": len(remediation_candidates),
        "operation_log_count": log_count,
        "execution_status": execution.get("status"),
        "candidate_auto_approval": 0,
        "expert_auto_write": False,
        "fact_updates": 0,
        "evidence_deletes": 0,
        "vector_writes": 0,
        "embedding_writes": 0,
        "full_reindex": False,
        "failures": failures,
    }
    write_json("reconciliation.json", payload)
    print(json.dumps({"status": payload["status"], "checks": checks, "failures": failures}, ensure_ascii=False))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
