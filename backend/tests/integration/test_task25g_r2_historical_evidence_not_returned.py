import json

from app.core.database import SessionLocal
from app.services.knowledge_graph_service import KnowledgeGraphService
from task25g_r2_common import RUNTIME


def test_all_frozen_historical_evidence_remains_excluded_from_production_context():
    baseline = json.loads((RUNTIME / "active_fact_baseline.json").read_text(encoding="utf-8"))
    historical_ids = {item["evidence_id"] for item in baseline["evidence"]}
    with SessionLocal() as session:
        context = KnowledgeGraphService(session).business_context(question="逆变器告警排查", limit=80)
    returned = {item["id"] for item in context.get("evidence") or []}
    assert not returned.intersection(historical_ids)

