from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from create_task25g_r1_remediation_plan import evidence_state, fact_state
from task25g_r1_common import now_iso, read_json, sha256_value, write_json


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply the frozen Task 25G-R1 grounding remediation plan")
    parser.add_argument(
        "--apply-approved-remediation",
        action="store_true",
        help="apply engineering remediation; this does not grant expert approval",
    )
    return parser.parse_args()


def _verify_old_state(session: Any, operation: dict[str, Any]) -> None:
    from app.models import KGEdge, KGEvidenceLink, KGNode

    target_id = UUID(operation["target_id"])
    if operation["target_type"] == "kg_evidence_link":
        target = session.get(KGEvidenceLink, target_id)
        current = evidence_state(target) if target else None
    else:
        model = KGNode if operation["target_type"] == "node" else KGEdge
        target = session.get(model, target_id)
        current = fact_state(target, operation["target_type"]) if target else None
    if sha256_value(current) != operation["old_state_hash"]:
        raise RuntimeError(f"old_state_hash mismatch for {operation['target_type']}:{operation['target_id']}")


def _logical_candidate(candidate: Any) -> dict[str, Any]:
    payload = candidate.payload_json or {}
    return {
        "target_type": payload.get("target_type"),
        "target_id": payload.get("target_id"),
        "candidate_type": candidate.candidate_type,
        "status": candidate.status,
        "production_grounding_status": payload.get("production_grounding_status"),
        "source_evidence_ids": sorted(payload.get("source_evidence_ids") or []),
        "expert_verified": bool(payload.get("expert_verified", False)),
    }


def _find_run(session: Any, plan_id: str) -> Any | None:
    from app.models import KGExtractionRun

    for run in session.scalars(
        select(KGExtractionRun).where(KGExtractionRun.source_type == "task25g_r1_remediation")
    ):
        if (run.metadata_json or {}).get("plan_id") == plan_id:
            return run
    return None


def _find_candidate(session: Any, run_id: UUID, desired: dict[str, Any]) -> Any | None:
    from app.models import KGCandidate

    for candidate in session.scalars(select(KGCandidate).where(KGCandidate.run_id == run_id)):
        payload = candidate.payload_json or {}
        if payload.get("target_type") == desired["target_type"] and payload.get("target_id") == desired["target_id"]:
            return candidate
    return None


def _operation_log_exists(session: Any, trace_id: str) -> bool:
    from app.models import OperationLog

    return session.scalar(select(OperationLog.id).where(OperationLog.trace_id == trace_id).limit(1)) is not None


def _log_operation(session: Any, operation: dict[str, Any], plan_id: str) -> bool:
    from app.models import OperationLog

    trace_id = f"kg-r1-{sha256_value([plan_id, operation['operation'], operation['target_id']])[:48]}"
    if _operation_log_exists(session, trace_id):
        return False
    session.add(
        OperationLog(
            module="knowledge_graph",
            action="task25g_r1_grounding_remediation",
            target_type=operation["target_type"],
            target_id=operation["target_id"],
            operator="engineering_remediation",
            request_id=plan_id[:64],
            trace_id=trace_id,
            detail={
                "operation": operation["operation"],
                "reason": operation["reason"],
                "source_evidence_ids": operation["source_evidence"],
                "old_state_hash": operation["old_state_hash"],
                "new_state_hash": operation["new_state_hash"],
                "expert_verified": False,
                "automatic_fact_write": False,
            },
        )
    )
    return True


def _dry_run(plan: dict[str, Any]) -> dict[str, Any]:
    from app.core.database import SessionLocal

    with SessionLocal() as session:
        for operation in plan["operations"]:
            _verify_old_state(session, operation)
    return {
        "version": "task25g_r1_remediation_execution_v1",
        "generated_at": now_iso(),
        "status": "DRY_RUN_PASS",
        "plan_id": plan["plan_id"],
        "apply_flag": False,
        "old_state_hashes_verified": len(plan["operations"]),
        "database_writes": 0,
        "candidate_writes": 0,
        "operation_log_writes": 0,
        "evidence_rebinds": 0,
        "evidence_deletes": 0,
        "fact_updates": 0,
        "expert_auto_write": False,
        "transaction_committed": False,
    }


def _apply(plan: dict[str, Any]) -> dict[str, Any]:
    from app.core.database import SessionLocal
    from app.models import KGCandidate, KGExtractionRun

    created_candidates: list[str] = []
    reused_candidates: list[str] = []
    operation_log_writes = 0
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        try:
            with session.begin():
                for operation in plan["operations"]:
                    _verify_old_state(session, operation)
                run = _find_run(session, plan["plan_id"])
                if run is None:
                    run = KGExtractionRun(
                        source_type="task25g_r1_remediation",
                        source_id=None,
                        extractor="engineering_remediation_v1",
                        status="completed",
                        candidate_count=0,
                        approved_count=0,
                        rejected_count=0,
                        started_at=now,
                        finished_at=now,
                        metadata_json={
                            "plan_id": plan["plan_id"],
                            "expert_verified": False,
                            "automatic_fact_write": False,
                        },
                    )
                    session.add(run)
                    session.flush()
                for operation in plan["operations"]:
                    if operation["operation"] == "CREATE_KG_REMEDIATION_CANDIDATE":
                        desired = operation["desired_candidate"]
                        candidate = _find_candidate(session, run.id, desired)
                        if candidate is None:
                            candidate = KGCandidate(
                                run_id=run.id,
                                candidate_type=desired["candidate_type"],
                                payload_json={
                                    **desired,
                                    "remediation_plan_id": plan["plan_id"],
                                    "approval_required": True,
                                    "automatic_fact_write": False,
                                },
                                status="pending",
                                confidence=1.0,
                                evidence_text=None,
                                reviewed_by=None,
                                reviewed_at=None,
                                review_comment=None,
                            )
                            session.add(candidate)
                            session.flush()
                            created_candidates.append(str(candidate.id))
                        else:
                            if sha256_value(_logical_candidate(candidate)) != operation["new_state_hash"]:
                                raise RuntimeError(f"existing remediation candidate state mismatch: {candidate.id}")
                            reused_candidates.append(str(candidate.id))
                    operation_log_writes += int(_log_operation(session, operation, plan["plan_id"]))
                run.candidate_count = len(created_candidates) + len(reused_candidates)
                run.finished_at = now
                session.add(run)
                session.flush()
                for operation in plan["operations"]:
                    if operation["operation"] != "CREATE_KG_REMEDIATION_CANDIDATE":
                        continue
                    desired = operation["desired_candidate"]
                    candidate = _find_candidate(session, run.id, desired)
                    if candidate is None or sha256_value(_logical_candidate(candidate)) != operation["new_state_hash"]:
                        raise RuntimeError(f"new_state_hash verification failed: {operation['target_id']}")
        except Exception:
            session.rollback()
            raise
    return {
        "version": "task25g_r1_remediation_execution_v1",
        "generated_at": now_iso(),
        "status": "APPLY_PASS",
        "plan_id": plan["plan_id"],
        "apply_flag": True,
        "old_state_hashes_verified": len(plan["operations"]),
        "new_state_hashes_verified": sum(
            item["operation"] == "CREATE_KG_REMEDIATION_CANDIDATE" for item in plan["operations"]
        ),
        "database_writes": len(created_candidates) + operation_log_writes,
        "candidate_writes": len(created_candidates),
        "candidate_reused": len(reused_candidates),
        "candidate_ids": sorted(created_candidates + reused_candidates),
        "operation_log_writes": operation_log_writes,
        "evidence_rebinds": 0,
        "evidence_deletes": 0,
        "fact_updates": 0,
        "expert_auto_write": False,
        "transaction_committed": True,
    }


def main() -> int:
    args = _parse_args()
    plan = read_json("remediation_plan.json", {})
    if not plan or plan.get("status") != "DRY_RUN_READY":
        raise SystemExit("Task 25G-R1 remediation plan is missing or invalid")
    result = _apply(plan) if args.apply_approved_remediation else _dry_run(plan)
    write_json("remediation_execution.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "apply_flag": result["apply_flag"],
                "candidate_writes": result["candidate_writes"],
                "operation_log_writes": result["operation_log_writes"],
                "expert_auto_write": result["expert_auto_write"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
