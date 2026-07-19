from app.models import KnowledgeDocument
from app.services.knowledge_graph_production_scope_service import KnowledgeGraphProductionScopeService


def document(**overrides):
    values = {
        "title": "Chinese inverter manual",
        "manufacturer": "huawei",
        "product_series": "SUN2000",
        "device_type": "pv_inverter",
        "document_type": "manual",
        "parse_status": "parsed",
        "review_status": "approved",
        "status": "active",
        "metadata_json": {
            "normalized_language": "zh-CN",
            "current_version": True,
            "approval_mode": "human_expert_approval",
        },
    }
    values.update(overrides)
    return KnowledgeDocument(**values)


def test_document_state_dimensions_are_classified_independently():
    archived = document(status="archived", document_type="maintenance_record")
    decision = KnowledgeGraphProductionScopeService.classify_document(archived)
    assert not decision.eligible
    assert "lifecycle_archived" in decision.reasons
    assert "marketing_document" not in decision.reasons
    assert not any(reason.startswith("approval_") for reason in decision.reasons)


def test_current_chinese_approved_document_is_eligible():
    assert KnowledgeGraphProductionScopeService.classify_document(document()).eligible

