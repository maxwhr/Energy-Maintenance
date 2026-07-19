from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select

from task25g_r2_common import now_iso, read_json, sha256_value, write_json


SOURCE_TYPE = "task25g_r2_current_fact_candidate"


def _find_run(session, manifest_hash: str):
    from app.models import KGExtractionRun

    for run in session.scalars(select(KGExtractionRun).where(KGExtractionRun.source_type == SOURCE_TYPE)):
        if (run.metadata_json or {}).get("core_manifest_sha256") == manifest_hash:
            return run
    return None


def _find_candidate(session, run_id, fact_id: str):
    from app.models import KGCandidate

    for candidate in session.scalars(select(KGCandidate).where(KGCandidate.run_id == run_id)):
        if (candidate.payload_json or {}).get("target_fact_id") == fact_id:
            return candidate
    return None


def _log(session, fact_id: str, manifest_hash: str) -> bool:
    from app.models import OperationLog

    trace_id = "kg-r2-review-" + sha256_value([manifest_hash, fact_id])[:40]
    if session.scalar(select(OperationLog.id).where(OperationLog.trace_id == trace_id).limit(1)):
        return False
    session.add(
        OperationLog(
            module="knowledge_graph",
            action="task25g_r2_create_manual_review_candidate",
            target_type="graph_fact",
            target_id=fact_id,
            operator="engineering_governance",
            request_id=manifest_hash[:64],
            trace_id=trace_id,
            detail={
                "status": "pending",
                "production_grounding_status": "UNSUPPORTED_CURRENT_SOURCE",
                "automatic_fact_write": False,
                "auto_approved": False,
                "expert_verified": False,
            },
        )
    )
    return True


def main() -> int:
    from app.core.database import SessionLocal
    from app.models import KGCandidate, KGExtractionRun

    manifest = read_json("production_core_fact_manifest.json", {})
    plan = read_json("grounding_plan.json", {})
    if not manifest or not plan:
        raise SystemExit("Task 25G-R2 manifest or grounding plan is missing")
    review_ops = [
        item for item in plan.get("operations") or [] if item["operation"] == "CREATE_MANUAL_REVIEW_CANDIDATE"
    ]
    created: list[str] = []
    reused: list[str] = []
    logs = 0
    now = datetime.now(timezone.utc)
    with SessionLocal() as session:
        with session.begin():
            run = _find_run(session, manifest["manifest_sha256"])
            if run is None:
                run = KGExtractionRun(
                    source_type=SOURCE_TYPE,
                    source_id=None,
                    extractor="deterministic_current_source_review_v1",
                    status="completed",
                    candidate_count=0,
                    approved_count=0,
                    rejected_count=0,
                    started_at=now,
                    finished_at=now,
                    metadata_json={
                        "core_manifest_sha256": manifest["manifest_sha256"],
                        "new_fact_candidates": 0,
                        "automatic_fact_write": False,
                        "expert_verified": False,
                    },
                )
                session.add(run)
                session.flush()
            for operation in review_ops:
                candidate = _find_candidate(session, run.id, operation["fact_id"])
                if candidate is None:
                    candidate = KGCandidate(
                        run_id=run.id,
                        candidate_type="task25g_r2_current_source_review",
                        payload_json={
                            "target_fact_id": operation["fact_id"],
                            "production_grounding_status": "UNSUPPORTED_CURRENT_SOURCE",
                            "reason": "no direct current Chinese engineering evidence",
                            "core_manifest_sha256": manifest["manifest_sha256"],
                            "approval_required": True,
                            "automatic_fact_write": False,
                            "expert_verified": False,
                        },
                        status="pending",
                        confidence=0.0,
                        evidence_text=None,
                    )
                    session.add(candidate)
                    session.flush()
                    created.append(str(candidate.id))
                else:
                    if candidate.status != "pending" or candidate.reviewed_by is not None:
                        raise RuntimeError(f"existing Task 25G-R2 candidate was reviewed unexpectedly: {candidate.id}")
                    reused.append(str(candidate.id))
                logs += int(_log(session, operation["fact_id"], manifest["manifest_sha256"]))
            run.candidate_count = len(created) + len(reused)
            run.approved_count = 0
            run.rejected_count = 0
            run.finished_at = now
            session.add(run)
    payload = {
        "version": "task25g_r2_current_fact_candidates_v1",
        "generated_at": now_iso(),
        "status": "PENDING_MANUAL_REVIEW_CANDIDATES_CREATED",
        "core_gate_passed": bool((manifest.get("gate") or {}).get("passed")),
        "manual_review_candidate_count": len(created) + len(reused),
        "created_count": len(created),
        "reused_count": len(reused),
        "candidate_ids": sorted(created + reused),
        "new_fact_candidate_count": 0,
        "candidate_auto_approval": 0,
        "fact_auto_publication": 0,
        "expert_auto_write": False,
        "operation_log_writes": logs,
    }
    write_json("current_fact_candidates.json", payload)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
