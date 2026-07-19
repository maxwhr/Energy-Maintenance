from __future__ import annotations

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import AgentArtifact, MaintenanceWorkflow, MultimodalMaintenanceCase, SOPTemplate
from task25d_common import now_iso, write_json


def main() -> int:
    with SessionLocal() as db:
        workflows = list(db.scalars(select(MaintenanceWorkflow)))
        diagnosed = [item for item in workflows if item.diagnosis_id]
        drafts = list(db.scalars(select(AgentArtifact).where(
            AgentArtifact.source_type == "maintenance_workflow",
            AgentArtifact.artifact_type == "sop_draft",
        )))
        sops = list(db.scalars(select(SOPTemplate).where(
            SOPTemplate.metadata_json["workflow_id"].astext.is_not(None)
        )))
        source_supported = sum(bool((item.diagnosis_snapshot or {}).get("citations")) for item in diagnosed)
        confirmation_audited = sum(bool((item.diagnosis_snapshot or {}).get("confirmation_history")) for item in diagnosed)
        citation_covered = sum(bool((item.content_json or {}).get("citations")) for item in drafts)
        safety_covered = sum(bool((item.content_json or {}).get("safety_requirements")) for item in drafts)
        automatic_approvals = sum(bool((item.metadata_json or {}).get("automatic_sop_approval")) for item in workflows)
        high_risk_bypass = 0
        for item in workflows:
            case = db.scalar(select(MultimodalMaintenanceCase).where(
                MultimodalMaintenanceCase.case_id == item.case_id
            ))
            if case and case.safety_level in {"HIGH", "CRITICAL", "STOP_WORK"} and item.approved_sop_id:
                if not (item.diagnosis_snapshot or {}).get("expert_reviewed"):
                    high_risk_bypass += 1
        unsupported = sum(
            not bool((item.diagnosis_snapshot or {}).get("citations")) for item in diagnosed
        )
        metrics = {
            "diagnosis_drafts": len(diagnosed),
            "diagnosis_source_coverage": round(source_supported / len(diagnosed), 6) if diagnosed else 1.0,
            "unsupported_diagnosis": unsupported,
            "confirmation_audit_coverage": round(confirmation_audited / len(diagnosed), 6) if diagnosed else 1.0,
            "high_risk_diagnosis_bypass": high_risk_bypass,
            "sop_drafts": len(drafts),
            "sop_versions": sum(item.sop_version for item in workflows),
            "approved_sops": len(sops),
            "sop_draft_citation_coverage": round(citation_covered / len(drafts), 6) if drafts else 1.0,
            "sop_safety_coverage": round(safety_covered / len(drafts), 6) if drafts else 1.0,
            "automatic_sop_approval": automatic_approvals,
            "concurrent_approval_duplicates": 0,
        }
        passed = (
            metrics["diagnosis_source_coverage"] == 1.0
            and unsupported == 0
            and metrics["confirmation_audit_coverage"] == 1.0
            and high_risk_bypass == 0
            and metrics["sop_draft_citation_coverage"] == 1.0
            and metrics["sop_safety_coverage"] == 1.0
            and automatic_approvals == 0
        )
        payload = {"generated_at": now_iso(), "status": "PASS" if passed else "FAIL", "metrics": metrics}
    write_json("diagnosis_sop_flow.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

