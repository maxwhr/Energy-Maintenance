from app.core.database import SessionLocal
from app.services.knowledge_graph_service import KnowledgeGraphService


def test_every_returned_graph_fact_has_current_evidence_ids():
    with SessionLocal() as db:
        context = KnowledgeGraphService(db).business_context(question="SUN2000 逆变器", limit=80)
    evidence_ids = {str(item["id"]) for item in context.get("evidence") or []}
    for item in [*(context.get("kg_nodes") or []), *(context.get("kg_edges") or [])]:
        assert item.get("evidence_ids")
        assert set(item["evidence_ids"]).issubset(evidence_ids)

