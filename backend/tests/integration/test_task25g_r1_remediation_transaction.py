import json

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import KGCandidate, OperationLog
from task25g_r1_common import RUNTIME


def test_applied_remediation_is_idempotent_and_pending_review_only():
    plan = json.loads((RUNTIME / "remediation_plan.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        candidates = [
            item
            for item in db.scalars(select(KGCandidate).where(KGCandidate.candidate_type == "grounding_remediation"))
            if (item.payload_json or {}).get("remediation_plan_id") == plan["plan_id"]
        ]
        logs = list(
            db.scalars(
                select(OperationLog).where(
                    OperationLog.action == "task25g_r1_grounding_remediation",
                    OperationLog.request_id == plan["plan_id"][:64],
                )
            )
        )
    assert len(candidates) == 2
    assert all(item.status == "pending" and item.reviewed_by is None for item in candidates)
    assert len(logs) == plan["operation_count"]

