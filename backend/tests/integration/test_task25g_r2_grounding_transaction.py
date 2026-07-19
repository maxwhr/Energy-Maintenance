import json

import pytest
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import KGEvidenceLink
from scripts.apply_task25g_r2_grounding_plan import _apply
from task25g_r2_common import RUNTIME


def test_rejected_core_cannot_enter_grounding_transaction():
    manifest = json.loads((RUNTIME / "production_core_fact_manifest.json").read_text(encoding="utf-8"))
    plan = json.loads((RUNTIME / "grounding_plan.json").read_text(encoding="utf-8"))
    with SessionLocal() as session:
        before = session.scalar(
            select(func.count()).select_from(KGEvidenceLink).where(
                KGEvidenceLink.source_type == "task25g_r2_current_chinese_grounding"
            )
        )
        with pytest.raises(RuntimeError, match="production core gate"):
            _apply(session, manifest, plan)
        after = session.scalar(
            select(func.count()).select_from(KGEvidenceLink).where(
                KGEvidenceLink.source_type == "task25g_r2_current_chinese_grounding"
            )
        )
    assert before == after == 0
