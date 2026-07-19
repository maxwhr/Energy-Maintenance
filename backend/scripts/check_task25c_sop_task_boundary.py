from __future__ import annotations

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services.multimodal_sop_task_boundary_service import MultimodalSopTaskBoundaryService
from task25c_common import now_iso, read_json, write_json


def main() -> int:
    service = MultimodalSopTaskBoundaryService()
    sop_blocked = service.allow_sop_draft(
        device_model=None, user_confirmed_device=False, valid_citation_count=0,
        safety_complete=False, evidence_confidence=.4, open_high_conflicts=1,
    )
    sop_allowed = service.allow_sop_draft(
        device_model="SUN2000-50KTL-M3", user_confirmed_device=True, valid_citation_count=1,
        safety_complete=True, evidence_confidence=.9, open_high_conflicts=0,
    )
    task_blocked = service.allow_task_draft(sop_status="draft", sop_user_confirmed=False, safety_complete=True, role="engineer")
    task_allowed = service.allow_task_draft(sop_status="draft", sop_user_confirmed=True, safety_complete=True, role="engineer")
    with SessionLocal() as db:
        current = {
            "sop_templates": int(db.scalar(text("SELECT count(*) FROM sop_templates")) or 0),
            "maintenance_tasks": int(db.scalar(text("SELECT count(*) FROM maintenance_tasks")) or 0),
        }
        artifact_counts = {
            "sop_drafts": int(db.scalar(text(
                "SELECT count(*) FROM agent_artifacts a JOIN agent_runs r ON r.run_id=a.run_id "
                "WHERE a.artifact_type='sop_draft' AND r.agent_code LIKE 'task25c%'"
            )) or 0),
            "task_drafts": int(db.scalar(text(
                "SELECT count(*) FROM agent_artifacts a JOIN agent_runs r ON r.run_id=a.run_id "
                "WHERE a.artifact_type='task_draft' AND r.agent_code LIKE 'task25c%'"
            )) or 0),
        }
        task25c_approved = int(db.scalar(text(
            "SELECT count(*) FROM agent_approvals a JOIN agent_runs r ON r.run_id=a.run_id "
            "WHERE r.agent_code LIKE 'task25c%' AND a.status='approved'"
        )) or 0)
        task25c_conversions = int(db.scalar(text(
            "SELECT count(*) FROM agent_artifact_conversions c JOIN agent_runs r ON r.id=c.source_run_id "
            "WHERE r.agent_code LIKE 'task25c%'"
        )) or 0)
    checks = {
        "sop_blocks_missing_evidence": not sop_blocked.allowed,
        "sop_allows_only_draft": sop_allowed.allowed and sop_allowed.artifact_type == "sop_draft" and not sop_allowed.formal_record_created,
        "sop_requires_human_approval": sop_allowed.requires_human_approval,
        "task_requires_sop_confirmation": not task_blocked.allowed,
        "task_allows_only_draft": task_allowed.allowed and task_allowed.artifact_type == "task_draft" and not task_allowed.formal_record_created,
        "automatic_sop_approval_zero": task25c_approved == 0,
        "automatic_formal_task_zero": task25c_conversions == 0,
    }
    payload = {
        "generated_at": now_iso(), "status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
        "current_counts": current, "artifact_counts": artifact_counts,
        "task25c_approved_approvals": task25c_approved, "task25c_artifact_conversions": task25c_conversions,
        "automatic_sop_approvals": 0 if checks["automatic_sop_approval_zero"] else None,
        "automatic_formal_tasks": 0 if checks["automatic_formal_task_zero"] else None,
    }
    write_json("sop_task_boundary.json", payload)
    print(payload["status"])
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
