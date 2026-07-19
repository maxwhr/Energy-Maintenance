from app.models import KnowledgeDocument
from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService


def test_production_scope_rejects_non_chinese_and_superseded_documents():
    value = KnowledgeDocument(
        title="Legacy manual",
        manufacturer="huawei",
        device_type="pv_inverter",
        document_type="manual",
        parse_status="parsed",
        review_status="approved",
        status="active",
        metadata_json={
            "normalized_language": "en",
            "superseded_by_document_id": "00000000-0000-0000-0000-000000000001",
        },
    )
    decision = KnowledgeGraphProductionScopeService.classify_document(value)
    assert not decision.eligible
    assert "language_en" in decision.reasons
    assert "superseded_document" in decision.reasons

