import json

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import KGCandidate, KGEvidenceLink
from task25g_r2_common import RUNTIME


def test_current_chinese_grounding_is_blocked_and_review_candidates_are_pending():
    execution = json.loads((RUNTIME / "grounding_execution.json").read_text(encoding="utf-8"))
    assert execution["status"] == "DRY_RUN_GATE_BLOCKED"
    with SessionLocal() as session:
        links = session.scalar(
            select(func.count()).select_from(KGEvidenceLink).where(
                KGEvidenceLink.source_type == "task25g_r2_current_chinese_grounding"
            )
        )
        candidates = list(
            session.scalars(
                select(KGCandidate).where(KGCandidate.candidate_type == "task25g_r2_current_source_review")
            )
        )
    assert links == 0
    assert len(candidates) == 58
    assert all(item.status == "pending" and item.reviewed_by is None for item in candidates)

