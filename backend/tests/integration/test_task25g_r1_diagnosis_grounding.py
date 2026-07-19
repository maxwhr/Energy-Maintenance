import inspect

from app.core.database import SessionLocal
from app.services.diagnosis_service import DiagnosisService
from app.services.knowledge_graph_service import KnowledgeGraphService


def test_diagnosis_uses_the_same_scoped_graph_context():
    source = inspect.getsource(DiagnosisService._resolve_kg_context)
    assert "KnowledgeGraphService" in source
    assert ".business_context(" in source
    with SessionLocal() as db:
        context = KnowledgeGraphService(db).business_context(question="task25g-r1-unsupported-fact", limit=20)
    assert context["kg_nodes"] == []
    assert context["kg_edges"] == []
    assert context["evidence"] == []

