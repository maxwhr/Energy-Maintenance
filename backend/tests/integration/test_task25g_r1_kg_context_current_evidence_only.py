import json

from app.core.database import SessionLocal
from app.services.knowledge_graph_service import KnowledgeGraphService
from task25g_r1_common import RUNTIME


def test_business_context_excludes_frozen_archived_evidence():
    baseline = json.loads((RUNTIME / "leakage_baseline.json").read_text(encoding="utf-8"))
    leaked_ids = set(baseline["evidence_ids"])
    with SessionLocal() as db:
        context = KnowledgeGraphService(db).business_context(question="逆变器告警排查", limit=80)
    returned = {str(item["id"]) for item in context.get("evidence") or []}
    assert not returned.intersection(leaked_ids)
    assert all(item.get("scope_status") == "CURRENT_VALID" for item in context.get("evidence") or [])

