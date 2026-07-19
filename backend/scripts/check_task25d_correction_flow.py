from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import ModelOutputCorrection
from task25d_common import now_iso, write_json


def main() -> int:
    with SessionLocal() as db:
        items = list(db.scalars(select(ModelOutputCorrection).where(
            ModelOutputCorrection.source_type == "maintenance_workflow"
        )))
        evidence_covered = sum(bool((item.metadata_json or {}).get("evidence_ids")) for item in items)
        expert_auto_writes = sum(bool((item.metadata_json or {}).get("expert_verified")) for item in items)
        automatic_updates = sum(bool((item.metadata_json or {}).get("automatic_knowledge_update")) for item in items)
        metrics = {
            "correction_drafts": sum(item.review_status == "draft" for item in items),
            "pending_reviews": sum(item.review_status == "pending_review" for item in items),
            "approved": sum(item.review_status == "accepted" for item in items),
            "rejected": sum(item.review_status == "rejected" for item in items),
            "automatic_knowledge_updates": automatic_updates,
            "evidence_coverage": round(evidence_covered / len(items), 6) if items else 0.0,
            "expert_auto_writes": expert_auto_writes,
        }
        passed = bool(items) and metrics["evidence_coverage"] == 1.0 and automatic_updates == 0 and expert_auto_writes == 0
        payload = {"generated_at": now_iso(), "status": "PASS" if passed else "FAIL", "metrics": metrics}
    write_json("correction_flow.json", payload)
    print(payload["status"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

